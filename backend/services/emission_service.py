SCOPE_MAP = {
    "diesel": "Scope 1", "petrol": "Scope 1", "natural_gas": "Scope 1",
    "electricity": "Scope 2",
    "business_travel": "Scope 3", "employee_commuting": "Scope 3",
    "transportation": "Scope 3", "waste": "Scope 3", "supplier_emissions": "Scope 3",
}

def calculate_emission(quantity: float, factor: float) -> float:
    return round(quantity * factor, 4)

def scope_for(activity_type: str) -> str:
    return SCOPE_MAP[activity_type]
