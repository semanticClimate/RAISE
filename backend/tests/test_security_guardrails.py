import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.features.agent.tools import CypherSecurityGuardrail

def test_guardrails():
    # 1. Valid read-only query parameterization
    valid_q = "MATCH (p:Person)-[:PRINCIPAL_INVESTIGATOR]->(g:Grant) WHERE toLower(p.name) CONTAINS 'panigrahi' RETURN p, g LIMIT 10"
    res1 = CypherSecurityGuardrail.validate_and_parameterize(valid_q)
    print("=== Valid Query Parameterization ===")
    print("Parameterized Cypher:", res1["parameterized_query"])
    print("Extracted Params:", res1["params"])

    # 2. Mutating injection attempt (DETACH DELETE)
    injected_q = "MATCH (n) DETACH DELETE n // bypass"
    res2 = CypherSecurityGuardrail.validate_and_parameterize(injected_q)
    print("\n=== Mutating Injection Attempt ===")
    print("Valid:", res2["valid"])
    print("Blocked Reason:", res2.get("reason"))

    # 3. Administrative metadata exfiltration attempt
    admin_q = "CALL dbms.security.listUsers()"
    res3 = CypherSecurityGuardrail.validate_and_parameterize(admin_q)
    print("\n=== Admin Exfiltration Attempt ===")
    print("Valid:", res3["valid"])
    print("Blocked Reason:", res3.get("reason"))

if __name__ == "__main__":
    test_guardrails()
