"""Compare the unchanged HTTP listener under the same eight-client burst."""
from concurrent.futures import ThreadPoolExecutor
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import tarfile
import tempfile
import threading

spec = importlib.util.spec_from_file_location("qa_probes", Path(__file__).with_name("qa-probes.py"))
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)
BASELINE, COMMIT, EVIDENCE, PROJECT, REPORT = (
    probe.BASELINE, probe.COMMIT, probe.EVIDENCE, probe.PROJECT, probe.REPORT,
)
inventory, request, running_service = probe.inventory, probe.request, probe.running_service


results = []
with tempfile.TemporaryDirectory(prefix="qa-transport-") as directory:
    temporary = Path(directory)
    baseline = temporary / "baseline"
    baseline.mkdir()
    archive = subprocess.check_output(["git", "archive", BASELINE, "inventory"], cwd=PROJECT)
    with tarfile.open(fileobj=io.BytesIO(archive)) as bundle:
        bundle.extractall(baseline, filter="data")
    for revision, root in ((BASELINE, baseline), (COMMIT, PROJECT)):
        for attempt in range(3):
            with running_service(root, temporary / f"{revision[:7]}-{attempt}.sqlite3") as port:
                barrier = threading.Barrier(8)

                def reserve(number):
                    barrier.wait()
                    try:
                        return request(port, "POST", "/reservations", {
                            "order_id": f"burst-{number}", "sku": "DEMO", "quantity": 9,
                        })
                    except OSError as error:
                        return {"transport_error": f"{type(error).__name__}: {error}"}

                with ThreadPoolExecutor(max_workers=8) as executor:
                    responses = list(executor.map(reserve, range(8)))
                after = request(port, "GET", "/inventory/DEMO")
                assert sum(result.get("status") == 200 for result in responses) == 1
                assert all(result.get("status") in (200, 409) or "transport_error" in result for result in responses)
                assert after == inventory(10, 9, 1)
                row = {"commit": revision, "attempt": attempt + 1, "quantity": 9,
                       "responses": responses, "after": after}
                results.append(row)
                print(revision[:7], attempt + 1, "transport_errors", sum("transport_error" in response for response in responses))
(REPORT / "qa-transport-evidence.json").write_text(json.dumps({
    "results": results, "server_logs": EVIDENCE["server_logs"],
}, ensure_ascii=False, indent=2) + "\n")
