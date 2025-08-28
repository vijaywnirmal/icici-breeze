import sys
from pathlib import Path
from fastapi.testclient import TestClient
from src.app import app


OUTPUT_FILE = Path("verify_results.txt")


def main() -> int:
	client = TestClient(app)

	response_hello = client.get("/api/hello")
	response_health = client.get("/health")

	lines: list[str] = []
	all_ok = True

	if response_hello.status_code != 200:
		lines.append(f"/api/hello failed: {response_hello.status_code}")
		all_ok = False
	else:
		lines.append(f"/api/hello OK: {response_hello.json()}")

	if response_health.status_code != 200:
		lines.append(f"/health failed: {response_health.status_code}")
		all_ok = False
	else:
		lines.append(f"/health OK: {response_health.json()}")

	OUTPUT_FILE.write_text("\n".join(lines), encoding="utf-8")
	return 0 if all_ok else 1


if __name__ == "__main__":
	raise SystemExit(main())
