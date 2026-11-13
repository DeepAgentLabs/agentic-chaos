from agentic_chaos.chaos import TokenTimeoutError, chaos_call


def search(question):
    return [f"Document about {question}"]


try:
    result = chaos_call(search, "refund policy", faults=["token_timeout"], step_name="Search")
except TokenTimeoutError:
    result = []
print("Search result:", result)
