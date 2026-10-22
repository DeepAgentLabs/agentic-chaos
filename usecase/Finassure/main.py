"""FinAssure Server Entrypoint."""

import uvicorn
from finassure.config import settings

def main():
    print("=" * 60)
    print("  FINASSURE: Financial Multi-Agent Reliability Harness")
    print(f"  Dashboard running on: http://{settings.HOST}:{settings.PORT}")
    print(f"  Gemini API Key configured: {settings.has_gemini_key()}")
    print("=" * 60)
    uvicorn.run(
        "finassure.api.server:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=False,
    )

if __name__ == "__main__":
    main()
