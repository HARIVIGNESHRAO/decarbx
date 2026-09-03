import os
from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta, timezone
from typing import Literal

import jwt
from dotenv import load_dotenv
from bson import ObjectId
from fastapi import Depends, FastAPI, Header, HTTPException, Query, WebSocket, WebSocketDisconnect, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from pymongo import ASCENDING, DESCENDING, MongoClient
from pymongo.errors import DuplicateKeyError, PyMongoError
from pwdlib import PasswordHash
from pwdlib.hashers.bcrypt import BcryptHasher

from services.analytics_service import detect_anomalies, forecast, monthly_trends
from services.emission_service import SCOPE_MAP, calculate_emission, scope_for
from services.resource_service import RESOURCE_COLLECTIONS, can_access, create_audit, scoped_query, serialize

load_dotenv()

MONGODB_URL=os.getenv("MONGODB_URL","mongodb://localhost:27017")
DATABASE_NAME=os.getenv("MONGODB_DATABASE","decarbx")
JWT_SECRET=os.getenv("JWT_SECRET","dev-only-change-this-decarbx-secret")
JWT_ALGORITHM="HS256"
ACCESS_TOKEN_MINUTES=int(os.getenv("ACCESS_TOKEN_MINUTES","480"))
ORIGINS=os.getenv("FRONTEND_ORIGINS","http://localhost:5173,http://127.0.0.1:5173").split(",")
client=MongoClient(MONGODB_URL,serverSelectionTimeoutMS=2500)
db=client[DATABASE_NAME]
password_hash=PasswordHash((BcryptHasher(),))

ROLE_PERMISSIONS={
    "ADMIN":{"dashboard:read","emissions:read","emissions:create","emissions:update","emissions:delete","analytics:read","reports:read","users:manage","facilities:create","resources:read","resources:write","approve"},
    "SUSTAINABILITY_MANAGER":{"dashboard:read","emissions:read","emissions:create","emissions:update","analytics:read","reports:read","facilities:create","resources:read","resources:write","approve"},
    "CARBON_ANALYST":{"dashboard:read","emissions:read","emissions:create","emissions:update","analytics:read","reports:read","resources:read","resources:write"},
    "PROCUREMENT_MANAGER":{"dashboard:read","emissions:read","emissions:create","analytics:read","reports:read","resources:read","resources:write"},
    "FINANCE_USER":{"dashboard:read","emissions:read","analytics:read","reports:read","resources:read","resources:write"},
    "SUPPLIER":{"dashboard:read","emissions:read","emissions:create","resources:read","resources:write"},
    "AUDITOR":{"dashboard:read","emissions:read","analytics:read","reports:read","resources:read"},
    "VIEWER":{"dashboard:read","emissions:read","reports:read","resources:read"},
}

class LoginRequest(BaseModel): email:str; password:str
class FacilityCreate(BaseModel): name:str=Field(min_length=2,max_length=120); location:str=Field(min_length=2,max_length=120)
class EmissionInput(BaseModel):
    facility_id:str; activity_type:str=Field(pattern="^(electricity|diesel|petrol|natural_gas|business_travel|employee_commuting|transportation|waste|supplier_emissions)$"); quantity:float=Field(gt=0); unit:str=Field(min_length=1,max_length=30); reporting_date:date
Role=Literal["ADMIN","SUSTAINABILITY_MANAGER","CARBON_ANALYST","PROCUREMENT_MANAGER","FINANCE_USER","SUPPLIER","AUDITOR","VIEWER"]
class UserCreate(BaseModel):
    name:str=Field(min_length=2,max_length=100); email:str=Field(min_length=5,max_length=254); password:str=Field(min_length=8,max_length=128); role:Role
class UserUpdate(BaseModel): name:str|None=None; role:Role|None=None; active:bool|None=None
class ResourcePayload(BaseModel): data:dict

def oid(value:str, field:str="id") -> ObjectId:
    try:return ObjectId(value)
    except Exception as exc:raise HTTPException(422,f"Invalid {field}") from exc

def json_doc(doc:dict|None)->dict|None:
    if not doc:return None
    result={}
    for key,value in doc.items():
        if isinstance(value,ObjectId):result["id" if key=="_id" else key]=str(value)
        elif isinstance(value,datetime):result[key]=value.isoformat()
        else:result[key]=value
    return result

def public_user(user:dict)->dict:
    return {"id":str(user["_id"]),"name":user["name"],"email":user["email"],"role":user["role"],"active":user.get("active",True),"organization_id":str(user.get("organization_id","")),"supplier_id":str(user.get("supplier_id","")),"permissions":sorted(ROLE_PERMISSIONS[user["role"]])}

def create_token(user:dict)->str:
    now=datetime.now(timezone.utc)
    return jwt.encode({"sub":str(user["_id"]),"email":user["email"],"role":user["role"],"iat":now,"exp":now+timedelta(minutes=ACCESS_TOKEN_MINUTES)},JWT_SECRET,algorithm=JWT_ALGORITHM)

def decode_token(token:str)->dict:
    try:return jwt.decode(token,JWT_SECRET,algorithms=[JWT_ALGORITHM])
    except jwt.PyJWTError as exc:raise HTTPException(401,"Invalid or expired session") from exc

def current_user(authorization:str|None=Header(default=None))->dict:
    if not authorization or not authorization.startswith("Bearer "):raise HTTPException(401,"Authentication required")
    claims=decode_token(authorization.removeprefix("Bearer "))
    user=db.users.find_one({"_id":oid(claims["sub"]),"active":{"$ne":False}})
    if not user:raise HTTPException(401,"User is inactive or missing")
    return user

def require(permission:str):
    def check(user:dict=Depends(current_user)):
        if permission not in ROLE_PERMISSIONS[user["role"]]:raise HTTPException(403,"Your role does not have permission for this action")
        return user
    return check

class Connections:
    def __init__(self):self.sockets=[]
    async def connect(self,socket):await socket.accept();self.sockets.append(socket)
    def disconnect(self,socket):
        if socket in self.sockets:self.sockets.remove(socket)
    async def broadcast(self,message):
        for socket in self.sockets.copy():
            try:await socket.send_json(message)
            except Exception:self.disconnect(socket)
connections=Connections()

def indexes():
    db.users.create_index("email",unique=True);db.facilities.create_index("name",unique=True);db.emission_factors.create_index([("activity_type",ASCENDING),("unit",ASCENDING)])
    db.emission_records.create_index("reporting_date");db.emission_records.create_index("facility_id");db.emission_records.create_index("scope");db.emission_records.create_index("activity_type")

@asynccontextmanager
async def lifespan(_:FastAPI):
    try:client.admin.command("ping");indexes()
    except PyMongoError as exc:print(f"MongoDB unavailable: {exc}")
    yield;client.close()

app=FastAPI(title="DecarbX Environmental Intelligence API",version="2.0.0",lifespan=lifespan)
app.add_middleware(CORSMiddleware,allow_origins=ORIGINS,allow_credentials=True,allow_methods=["*"],allow_headers=["*"])

@app.get("/api/health")
def health():
    try:client.admin.command("ping");return {"status":"healthy","database":"connected","websocket_clients":len(connections.sockets)}
    except PyMongoError:return {"status":"degraded","database":"disconnected"}

@app.post("/api/auth/login")
def login(body:LoginRequest):
    user=db.users.find_one({"email":body.email.strip().lower(),"active":{"$ne":False}})
    if not user or not password_hash.verify(body.password,user["password_hash"]):raise HTTPException(401,"Incorrect email or password")
    return {"access_token":create_token(user),"token_type":"bearer","user":public_user(user)}

@app.get("/api/auth/me")
def me(user=Depends(current_user)):return public_user(user)

@app.get("/api/facilities")
def facilities(_:dict=Depends(require("emissions:read"))):return [json_doc(x) for x in db.facilities.find().sort("name")]

@app.post("/api/facilities",status_code=201)
def add_facility(body:FacilityCreate,_:dict=Depends(require("facilities:create"))):
    document=body.model_dump()|{"created_at":datetime.now(timezone.utc)}
    try:document["_id"]=db.facilities.insert_one(document).inserted_id
    except DuplicateKeyError as exc:raise HTTPException(409,"Facility already exists") from exc
    return json_doc(document)

def enriched_record(record:dict)->dict:
    result=json_doc(record);facility=db.facilities.find_one({"_id":record["facility_id"]});user=db.users.find_one({"_id":record["created_by"]})
    result["facility"]=facility["name"] if facility else "Unknown";result["created_by_name"]=user["name"] if user else "Unknown"
    return result

@app.post("/api/emissions/calculate",status_code=201)
async def calculate(body:EmissionInput,user=Depends(require("emissions:create"))):
    facility=db.facilities.find_one({"_id":oid(body.facility_id,"facility_id")})
    if not facility:raise HTTPException(404,"Facility not found")
    factor=db.emission_factors.find_one({"activity_type":body.activity_type,"unit":body.unit})
    if not factor:raise HTTPException(404,"No emission factor matches this activity type and unit")
    now=datetime.now(timezone.utc);activity={"organization_id":user.get("organization_id"),"entity_id":None,"facility_id":facility["_id"],"department_id":None,"cost_center_id":None,"source_type":"manual","activity_type":body.activity_type,"scope":scope_for(body.activity_type),"scope3_category":None,"quantity":body.quantity,"unit":body.unit,"reporting_period":body.reporting_date.isoformat(),"supplier_id":user.get("supplier_id"),"product_id":None,"data_source":"manual_form","created_by":user["_id"],"created_at":now};activity["_id"]=db.activity_data.insert_one(activity).inserted_id
    calculation={"organization_id":user.get("organization_id"),"activity_id":activity["_id"],"factor_id":factor["_id"],"factor_version":factor.get("version","unversioned"),"original_quantity":body.quantity,"original_unit":body.unit,"converted_quantity":body.quantity,"converted_unit":body.unit,"formula":f"{body.quantity} × {factor['factor']}","calculated_emission":calculate_emission(body.quantity,factor["factor"]),"emission_unit":"kgCO2e","scope":scope_for(body.activity_type),"allocation":1.0,"assumptions":[],"uncertainty":None,"calculation_version":1,"status":"CALCULATED","created_by":user["_id"],"created_at":now};calculation["_id"]=db.calculations.insert_one(calculation).inserted_id
    document=body.model_dump();document.update({"organization_id":user.get("organization_id"),"activity_id":activity["_id"],"calculation_id":calculation["_id"],"facility_id":facility["_id"],"scope":scope_for(body.activity_type),"emission_factor":factor["factor"],"factor_source":factor["source"],"factor_is_demo":factor.get("is_demo",False),"calculated_emission":calculation["calculated_emission"],"emission_unit":"kgCO2e","created_by":user["_id"],"created_at":now,"updated_at":now})
    document["reporting_date"]=datetime.combine(body.reporting_date,datetime.min.time(),tzinfo=timezone.utc);document["_id"]=db.emission_records.insert_one(document).inserted_id
    create_audit(db,user,"CREATE","emission_record",document["_id"],new=json_doc(document))
    create_audit(db,user,"CALCULATE","calculation",calculation["_id"],new=serialize(calculation));result=enriched_record(document);result["activity_id"]=str(activity["_id"]);result["calculation_id"]=str(calculation["_id"]);await connections.broadcast({"type":"emission_created","data":result});return result

@app.get("/api/emissions")
def emission_history(scope:str|None=None,activity_type:str|None=None,facility_id:str|None=None,date_from:date|None=None,date_to:date|None=None,_:dict=Depends(require("emissions:read"))):
    query={}
    if scope:query["scope"]=scope
    if activity_type:query["activity_type"]=activity_type
    if facility_id:query["facility_id"]=oid(facility_id,"facility_id")
    if date_from or date_to:
        query["reporting_date"]={}
        if date_from:query["reporting_date"]["$gte"]=datetime.combine(date_from,datetime.min.time(),tzinfo=timezone.utc)
        if date_to:query["reporting_date"]["$lte"]=datetime.combine(date_to,datetime.max.time(),tzinfo=timezone.utc)
    return [enriched_record(x) for x in db.emission_records.find(query).sort("reporting_date",DESCENDING)]

@app.get("/api/emissions/{record_id}")
def get_emission(record_id:str,_:dict=Depends(require("emissions:read"))):
    record=db.emission_records.find_one({"_id":oid(record_id)}); 
    if not record:raise HTTPException(404,"Emission record not found")
    return enriched_record(record)

@app.put("/api/emissions/{record_id}")
async def update_emission(record_id:str,body:EmissionInput,_:dict=Depends(require("emissions:update"))):
    factor=db.emission_factors.find_one({"activity_type":body.activity_type,"unit":body.unit})
    if not factor:raise HTTPException(404,"Matching emission factor not found")
    update=body.model_dump()|{"facility_id":oid(body.facility_id,"facility_id"),"reporting_date":datetime.combine(body.reporting_date,datetime.min.time(),tzinfo=timezone.utc),"scope":scope_for(body.activity_type),"emission_factor":factor["factor"],"calculated_emission":calculate_emission(body.quantity,factor["factor"]),"updated_at":datetime.now(timezone.utc)}
    record=db.emission_records.find_one_and_update({"_id":oid(record_id)},{"$set":update},return_document=True)
    if not record:raise HTTPException(404,"Emission record not found")
    result=enriched_record(record);await connections.broadcast({"type":"emission_updated","data":result});return result

@app.delete("/api/emissions/{record_id}",status_code=204)
async def delete_emission(record_id:str,_:dict=Depends(require("emissions:delete"))):
    if not db.emission_records.delete_one({"_id":oid(record_id)}).deleted_count:raise HTTPException(404,"Emission record not found")
    await connections.broadcast({"type":"emission_deleted","id":record_id})

def records():return list(db.emission_records.find())
def summary_data():
    all_records=records();scopes={"Scope 1":0.0,"Scope 2":0.0,"Scope 3":0.0};activities={};facilities_map={}
    for item in all_records:
        tonnes=item["calculated_emission"]/1000;scopes[item["scope"]]+=tonnes;activities[item["activity_type"]]=activities.get(item["activity_type"],0)+tonnes
        facility=db.facilities.find_one({"_id":item["facility_id"]});name=facility["name"] if facility else "Unknown";facilities_map[name]=facilities_map.get(name,0)+tonnes
    total=sum(scopes.values());largest=max(activities,key=activities.get) if activities else None
    return {"total_emissions":round(total,3),"scope_1":round(scopes["Scope 1"],3),"scope_2":round(scopes["Scope 2"],3),"scope_3":round(scopes["Scope 3"],3),"percentage_change":0,"total_records":len(all_records),"largest_source":largest,"by_activity":[{"name":k,"emissions":round(v,3)} for k,v in activities.items()],"by_facility":[{"name":k,"emissions":round(v,3)} for k,v in facilities_map.items()],"recent_records":[enriched_record(x) for x in sorted(all_records,key=lambda x:x["reporting_date"],reverse=True)[:5]]}

@app.get("/api/dashboard/summary")
def dashboard_summary(_:dict=Depends(require("dashboard:read"))):return summary_data()|{"trends":monthly_trends(records())}
@app.get("/api/analytics/trends")
def trends(_:dict=Depends(require("analytics:read"))):return monthly_trends(records())
@app.get("/api/analytics/anomalies")
def anomalies(_:dict=Depends(require("analytics:read"))):return detect_anomalies(records())
@app.get("/api/analytics/forecast")
def forecast_api(months:int=Query(3,ge=1,le=12),_:dict=Depends(require("analytics:read"))):return forecast(monthly_trends(records()),months)
@app.get("/api/reports/summary")
def report(_:dict=Depends(require("reports:read"))):return {"reporting_period":"All available data"}|summary_data()

@app.get("/api/users")
def list_users(_:dict=Depends(require("users:manage"))):return [public_user(x) for x in db.users.find().sort("name")]
@app.post("/api/users",status_code=201)
def add_user(body:UserCreate,_:dict=Depends(require("users:manage"))):
    document={"name":body.name,"email":body.email.lower(),"role":body.role,"password_hash":password_hash.hash(body.password),"active":True,"created_at":datetime.now(timezone.utc)}
    try:document["_id"]=db.users.insert_one(document).inserted_id
    except DuplicateKeyError as exc:raise HTTPException(409,"Email already exists") from exc
    return public_user(document)
@app.put("/api/users/{user_id}")
def update_user(user_id:str,body:UserUpdate,_:dict=Depends(require("users:manage"))):
    values={k:v for k,v in body.model_dump().items() if v is not None};user=db.users.find_one_and_update({"_id":oid(user_id)},{"$set":values},return_document=True)
    if not user:raise HTTPException(404,"User not found")
    return public_user(user)
@app.delete("/api/users/{user_id}",status_code=204)
def delete_user(user_id:str,admin=Depends(require("users:manage"))):
    target=oid(user_id)
    if target==admin["_id"]:raise HTTPException(400,"You cannot delete your own account")
    if not db.users.delete_one({"_id":target}).deleted_count:raise HTTPException(404,"User not found")

@app.get("/api/resources/{resource}")
def list_resource(resource:str,user=Depends(require("resources:read"))):
    if resource not in RESOURCE_COLLECTIONS:raise HTTPException(404,"Unknown platform resource")
    if not can_access(user,resource):raise HTTPException(403,"Your role cannot access this module")
    query={} if resource=="organizations" and user["role"]=="ADMIN" else scoped_query(user)
    return [serialize(x) for x in db[RESOURCE_COLLECTIONS[resource]].find(query).sort("created_at",DESCENDING).limit(500)]

@app.post("/api/resources/{resource}",status_code=201)
def create_resource(resource:str,body:ResourcePayload,user=Depends(require("resources:write"))):
    if resource not in RESOURCE_COLLECTIONS or resource=="audit-trail":raise HTTPException(404,"Resource is not writable")
    if not can_access(user,resource,"write"):raise HTTPException(403,"Your role cannot modify this module")
    document=body.data|{"organization_id":user.get("organization_id"),"created_by":user["_id"],"created_at":datetime.now(timezone.utc)}
    if user["role"]=="SUPPLIER":document["supplier_id"]=user.get("supplier_id")
    result=db[RESOURCE_COLLECTIONS[resource]].insert_one(document);create_audit(db,user,"CREATE",resource,result.inserted_id,new=serialize(document))
    return serialize(document|{"_id":result.inserted_id})

@app.put("/api/resources/{resource}/{item_id}")
def update_resource(resource:str,item_id:str,body:ResourcePayload,user=Depends(require("resources:write"))):
    if resource not in RESOURCE_COLLECTIONS or resource=="audit-trail":raise HTTPException(404,"Resource is not writable")
    if not can_access(user,resource,"write"):raise HTTPException(403,"Your role cannot modify this module")
    query=scoped_query(user)|{"_id":oid(item_id)};previous=db[RESOURCE_COLLECTIONS[resource]].find_one(query)
    if not previous:raise HTTPException(404,"Record not found or outside your access scope")
    values=body.data|{"updated_at":datetime.now(timezone.utc)};db[RESOURCE_COLLECTIONS[resource]].update_one(query,{"$set":values});create_audit(db,user,"UPDATE",resource,previous["_id"],serialize(previous),serialize(values))
    return serialize(db[RESOURCE_COLLECTIONS[resource]].find_one(query))

@app.get("/api/search")
def global_search(q:str=Query(min_length=2),user=Depends(require("resources:read"))):
    results=[]
    for resource in ["entities","facilities","activity-data","products","suppliers","emission-factors","calculations","disclosures","evidence","reduction-projects"]:
        collection=db[RESOURCE_COLLECTIONS[resource]];query=scoped_query(user)|{"$or":[{"name":{"$regex":q,"$options":"i"}},{"description":{"$regex":q,"$options":"i"}},{"activity_type":{"$regex":q,"$options":"i"}}]}
        results.extend([{"resource":resource,"record":serialize(x)} for x in collection.find(query).limit(10)])
    return results

@app.websocket("/ws/dashboard")
async def websocket(socket:WebSocket,token:str|None=None):
    try:
        claims=decode_token(token or "");user=db.users.find_one({"_id":oid(claims["sub"]),"active":{"$ne":False}})
        if not user:raise HTTPException(401,"Unauthorized")
    except HTTPException:await socket.close(code=4401);return
    await connections.connect(socket)
    try:
        while True:await socket.receive_text()
    except WebSocketDisconnect:connections.disconnect(socket)
