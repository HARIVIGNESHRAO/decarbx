from collections import defaultdict
from datetime import datetime
from math import sqrt

def monthly_trends(records: list[dict]) -> list[dict]:
    totals = defaultdict(float)
    for record in records:
        date = record["reporting_date"]
        if isinstance(date, str): date = datetime.fromisoformat(date)
        totals[date.strftime("%Y-%m")] += record["calculated_emission"] / 1000
    return [{"month": month, "emissions": round(value, 3)} for month, value in sorted(totals.items())]

def detect_anomalies(records: list[dict]) -> list[dict]:
    if len(records) < 2: return []
    values = [r["calculated_emission"] for r in records]
    average = sum(values) / len(values)
    deviation = sqrt(sum((v-average)**2 for v in values) / len(values))
    threshold = average + 2 * deviation
    return [{"id":str(r["_id"]),"value":r["calculated_emission"],"is_anomaly":True,"message":"Emission level is unusually high compared with historical data."} for r in records if r["calculated_emission"] > threshold]

def forecast(trends: list[dict], months: int = 3) -> list[dict]:
    if not trends: return []
    values = [point["emissions"] for point in trends]
    n = len(values)
    if n == 1: slope = 0
    else:
        x_mean = (n-1)/2; y_mean = sum(values)/n
        slope = sum((i-x_mean)*(v-y_mean) for i,v in enumerate(values)) / sum((i-x_mean)**2 for i in range(n))
    last = datetime.strptime(trends[-1]["month"], "%Y-%m")
    result=[]
    for step in range(1,months+1):
        month_index=last.month-1+step; year=last.year+month_index//12; month=month_index%12+1
        result.append({"month":f"{year:04d}-{month:02d}","predicted_emission":round(max(0,values[-1]+slope*step),3)})
    return result
