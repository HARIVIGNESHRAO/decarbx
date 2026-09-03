from datetime import datetime, timezone
from bson import ObjectId

RESOURCE_COLLECTIONS={
 "organizations":"organizations","entities":"entities","facilities":"facilities","departments":"departments","cost-centers":"cost_centers","reporting-boundaries":"reporting_boundaries",
 "emission-factors":"emission_factors","activity-data":"activity_data","calculations":"calculations","products":"products","product-lca":"product_carbon_footprints",
 "suppliers":"suppliers","supplier-submissions":"supplier_submissions","supplier-scorecards":"supplier_scorecards","data-quality":"data_quality_tasks","scenarios":"scenarios",
 "reduction-projects":"reduction_projects","carbon-finance":"carbon_projects","compliance":"disclosures","disclosures":"disclosure_data_points","evidence":"evidence",
 "audit-trail":"audit_logs","bulk-import":"import_jobs","integrations":"integrations","notifications":"notifications",
}
ROLE_RESOURCE_ACCESS={
 "ADMIN":{"read":"*","write":"*"},
 "SUSTAINABILITY_MANAGER":{"read":{"organizations","entities","facilities","departments","cost-centers","reporting-boundaries","emission-factors","activity-data","calculations","products","product-lca","suppliers","supplier-submissions","supplier-scorecards","data-quality","scenarios","reduction-projects","compliance","disclosures","evidence","audit-trail","notifications"},"write":{"activity-data","calculations","scenarios","reduction-projects","compliance","disclosures","evidence","data-quality"}},
 "CARBON_ANALYST":{"read":{"facilities","emission-factors","activity-data","calculations","data-quality","audit-trail","evidence"},"write":{"emission-factors","activity-data","calculations","data-quality","evidence"}},
 "PROCUREMENT_MANAGER":{"read":{"suppliers","supplier-submissions","supplier-scorecards","evidence","activity-data","reduction-projects","notifications"},"write":{"suppliers","supplier-submissions","supplier-scorecards","evidence","reduction-projects"}},
 "FINANCE_USER":{"read":{"carbon-finance","reduction-projects","calculations","reports","audit-trail"},"write":{"carbon-finance","reduction-projects"}},
 "SUPPLIER":{"read":{"supplier-submissions","supplier-scorecards","evidence","activity-data","notifications"},"write":{"supplier-submissions","evidence","activity-data"}},
 "AUDITOR":{"read":{"calculations","emission-factors","evidence","compliance","disclosures","audit-trail","data-quality"},"write":set()},
 "VIEWER":{"read":set(),"write":set()},
}

def can_access(user,resource,mode="read"):
 allowed=ROLE_RESOURCE_ACCESS[user["role"]][mode]
 return allowed=="*" or resource in allowed

def create_audit(db,user,action,object_type,object_id,previous=None,new=None):
 db.audit_logs.insert_one({"organization_id":user.get("organization_id"),"user_id":user["_id"],"action":action,"object_type":object_type,"object_id":object_id,"previous_value":previous,"new_value":new,"timestamp":datetime.now(timezone.utc)})

def serialize(value):
 if isinstance(value,ObjectId):return str(value)
 if isinstance(value,datetime):return value.isoformat()
 if isinstance(value,list):return [serialize(x) for x in value]
 if isinstance(value,dict):return {("id" if k=="_id" else k):serialize(v) for k,v in value.items()}
 return value

def scoped_query(user):
 query={"organization_id":user.get("organization_id")}
 if user["role"]=="SUPPLIER":query["supplier_id"]=user.get("supplier_id")
 return query
