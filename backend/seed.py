"""Explicit development seed. Run once with: python seed.py"""
from datetime import datetime, timezone
from main import db, indexes, password_hash

USERS=[("Admin User","admin@decarbx.com","Admin@123","ADMIN"),("Sustainability Manager","manager@decarbx.com","Manager@123","SUSTAINABILITY_MANAGER"),("Carbon Analyst","analyst@decarbx.com","Analyst@123","CARBON_ANALYST"),("Procurement Manager","procurement@decarbx.com","Procure@123","PROCUREMENT_MANAGER"),("Finance User","finance@decarbx.com","Finance@123","FINANCE_USER"),("Supplier User","supplier@decarbx.com","Supplier@123","SUPPLIER"),("External Auditor","auditor@decarbx.com","Auditor@123","AUDITOR"),("Report Viewer","viewer@decarbx.com","Viewer@123","VIEWER")]
FACILITIES=[("Hyderabad Factory","Hyderabad"),("Bangalore Office","Bangalore")]
FACTORS=[
    ("electricity","kWh",0.7,"Scope 2"),("diesel","litre",2.68,"Scope 1"),("petrol","litre",2.31,"Scope 1"),("natural_gas","m3",2.02,"Scope 1"),
    ("business_travel","km",0.15,"Scope 3"),("employee_commuting","km",0.12,"Scope 3"),("transportation","tonne-km",0.09,"Scope 3"),("waste","kg",0.46,"Scope 3"),("supplier_emissions","kg",1.0,"Scope 3"),
]
indexes()
organization=db.organizations.find_one_and_update({"name":"Nexgile-DecarbX"},{"$setOnInsert":{"name":"Nexgile-DecarbX","baseline_year":2025,"ownership_model":"Operational control","created_at":datetime.now(timezone.utc)}},upsert=True,return_document=True)
org_id=organization["_id"]
for name,email,password,role in USERS:
    db.users.update_one({"email":email},{"$set":{"name":name,"email":email,"password_hash":password_hash.hash(password),"role":role,"organization_id":org_id,"active":True,"created_at":datetime.now(timezone.utc)}},upsert=True)
for name,location in FACILITIES:
    db.facilities.update_one({"name":name},{"$set":{"name":name,"location":location,"organization_id":org_id,"created_at":datetime.now(timezone.utc)}},upsert=True)
for activity,unit,factor,scope in FACTORS:
    db.emission_factors.update_one({"activity_type":activity,"unit":unit},{"$set":{"organization_id":org_id,"name":activity.replace('_',' ').title()+" demo factor","activity_type":activity,"category":activity,"input_unit":unit,"output_unit":"kgCO2e","factor":factor,"scope":scope,"country":"DEMO","region":"DEMO","valid_from":datetime(2025,1,1,tzinfo=timezone.utc),"valid_to":datetime(2030,1,1,tzinfo=timezone.utc),"version":"demo-v1","source":"DEMO — not an official regulatory factor","is_demo":True,"created_at":datetime.now(timezone.utc)}},upsert=True)
print("Seed complete: organization, 8 roles, 2 facilities, 9 explicitly demo-labelled factors.")
