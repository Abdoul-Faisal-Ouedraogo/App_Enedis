"""Exécuter les notebooks ML sans autoriser réseau, entraînement ou sauvegarde."""
import contextlib
import io
import json
from pathlib import Path
import sys
from unittest.mock import patch

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from IPython.display import display


def forbidden(*args, **kwargs):
    raise AssertionError("Réseau, entraînement ou sauvegarde interdit pendant la vérification")


root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root))
for filename in ["2_classification_dpe.ipynb", "3_regression_consommation.ipynb"]:
    path = root / "Notebooks_Api_Traitement" / filename
    notebook = json.loads(path.read_text(encoding="utf-8"))
    namespace = {"display": display, "__name__": "__notebook__"}
    with (patch("requests.sessions.Session.request", forbidden),
          patch("sklearn.pipeline.Pipeline.fit", forbidden),
          patch("joblib.dump", forbidden),
          patch.object(plt, "show", lambda: plt.close("all"))):
        for index, cell in enumerate(notebook["cells"]):
            if cell["cell_type"] != "code":
                continue
            output = io.StringIO()
            try:
                with contextlib.redirect_stdout(output):
                    exec(compile("".join(cell["source"]), f"{filename}:cell{index}", "exec"), namespace)
            except Exception as exc:
                raise RuntimeError(f"{filename}, cellule {index}") from exc
            cell["execution_count"] = index
            cell["outputs"] = ([{"name": "stdout", "output_type": "stream", "text": output.getvalue().splitlines(True)}]
                               if output.getvalue() else [])
    path.write_text(json.dumps(notebook, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"OK : {filename}, cellules exécutées sans réseau, fit ou dump", flush=True)
