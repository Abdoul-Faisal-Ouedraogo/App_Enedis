"""Cadrage Mercator selon dimensions et conservation de la caméra native."""
import json
import shutil
import subprocess
from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

from src.project_paths import ROOT, DATA_PATH
from src.app_services import read_data, map_view
from src.app_map import update_camera, MEASURE_JS


@pytest.fixture(scope="module")
def data():
    return read_data(DATA_PATH)


def admissible(frame):
    return frame.loc[frame.lat.between(41, 51.5) & frame.lon.between(-5.5, 10)]


@pytest.mark.parametrize("departments", [None, ["69"], ["69", "75", "13"]])
@pytest.mark.parametrize("width,height", [(1200, 700), (360, 700), (900, 400)])
def test_all_filtered_points_fit_with_eight_percent_padding(data, departments, width, height):
    frame = data if departments is None else data[data.code_departement_ban.isin(departments)]
    valid = admissible(frame)
    view = map_view(frame, width, height)
    x = (valid.lon.to_numpy() - view.longitude) / 360 * 512 * 2 ** view.zoom
    mercator = lambda lat: np.degrees(np.arcsinh(np.tan(np.radians(lat))))
    y = (mercator(valid.lat.to_numpy()) - mercator(view.latitude)) / 360 * 512 * 2 ** view.zoom
    assert abs(x).max() <= width * .42 + 1e-6
    assert abs(y).max() <= height * .42 + 1e-6
    # La sélection remplit au moins un axe disponible : ni marge énorme ni zoom arbitraire.
    assert max(np.ptp(x) / width, np.ptp(y) / height) == pytest.approx(.84)


def test_rhone_uses_height_instead_of_old_320_pixel_square(data):
    frame = data[data.code_departement_ban.eq("69")]
    large = map_view(frame, 1200, 700)
    narrow = map_view(frame, 360, 700)
    short = map_view(frame, 1200, 350)
    assert large.zoom == pytest.approx(8.5673302611)
    assert narrow.zoom < large.zoom
    assert short.zoom == pytest.approx(large.zoom - 1)
    assert large.latitude == pytest.approx(45.8434887048)
    assert large.longitude == pytest.approx(4.7044395219)


def test_single_position_and_empty_selection(data):
    point = admissible(data).iloc[[0]]
    view = map_view(point, 360, 700)
    assert view.zoom == 14
    assert view.latitude == pytest.approx(point.lat.iloc[0])
    assert view.longitude == pytest.approx(point.lon.iloc[0])
    with pytest.raises(ValueError, match="Aucune coordonnée"):
        map_view(point.iloc[:0], 1200, 700)


def test_camera_only_changes_for_selection_first_measurement_or_recenter(data):
    rhone = data[data.code_departement_ban.eq("69")]
    initial = update_camera(None, rhone, 1000, 700, measured=False)
    measured = update_camera(initial, rhone, 1200, 700, measured=True)
    assert measured["generation"] == initial["generation"] + 1
    # Le resize ou un réglage d'affichage ne remplace pas la vue manuelle du navigateur.
    unchanged = update_camera(measured, rhone, 360, 700, measured=True)
    assert unchanged is measured
    recentered = update_camera(unchanged, rhone, 360, 700, recenter=True)
    assert recentered["generation"] == measured["generation"] + 1
    assert recentered["view"]["zoom"] < measured["view"]["zoom"]
    france = update_camera(recentered, data, 1200, 700)
    assert france["generation"] == recentered["generation"] + 1
    assert france["view"]["zoom"] < recentered["view"]["zoom"]
    assert update_camera(measured, rhone.iloc[::-1], 1200, 700) is measured
    # Même emprise, mais un logement en moins : la sélection doit aussi recentrer.
    new_selection = update_camera(measured, rhone.iloc[1:], 1200, 700)
    assert new_selection["generation"] == measured["generation"] + 1


def test_streamlit_camera_keys_across_filters_display_settings_and_recenter():
    with patch("src.app_map.map_dimensions", return_value=(1200, 700, True)):
        ui = AppTest.from_file(str(ROOT / "home.py"), default_timeout=90).run()
        ui.sidebar.radio[0].set_value("Carte").run()
        def chart():
            assert not ui.exception
            proto = ui.get("deck_gl_json_chart")[0].proto
            return proto.id, json.loads(proto.json)
        country_id, country = chart()
        ui.sidebar.multiselect[0].set_value(["69"]).run()
        rhone_id, rhone = chart()
        assert rhone_id != country_id
        assert rhone["initialViewState"]["zoom"] > country["initialViewState"]["zoom"] + 3
        [w for w in ui.checkbox if w.label.startswith("Afficher le fond")][0].check().run()
        assert chart()[0] == rhone_id
        assert chart()[1]["initialViewState"] == rhone["initialViewState"]
        ui.select_slider[0].set_value(1000).run()
        assert chart()[0] == rhone_id
        assert chart()[1]["initialViewState"] == rhone["initialViewState"]
        ui.button(key="recenter_map").click().run()
        assert chart()[0] != rhone_id
        assert chart()[1]["initialViewState"] == rhone["initialViewState"]
        ui.sidebar.multiselect[0].set_value(["69", "75"]).run()
        assert chart()[1]["initialViewState"]["zoom"] < rhone["initialViewState"]["zoom"]


def test_single_point_and_empty_filtered_selection_ui(data):
    point = admissible(data).iloc[[0]].copy()
    with patch("src.streamlit_app.cached_data", return_value=point), patch("src.app_map.map_dimensions", return_value=(360, 700, True)):
        ui = AppTest.from_file(str(ROOT / "home.py"), default_timeout=90).run()
        ui.sidebar.radio[0].set_value("Carte").run()
        assert not ui.exception
        assert json.loads(ui.get("deck_gl_json_chart")[0].proto.json)["initialViewState"]["zoom"] == 14
    # Deux surfaces distinctes pour autoriser une sélection vide par le curseur.
    small = pd.concat([point, point], ignore_index=True)
    small["surface_habitable_logement"] = [50.0, 100.0]
    with patch("src.streamlit_app.cached_data", return_value=small):
        ui = AppTest.from_file(str(ROOT / "home.py"), default_timeout=90).run()
        ui.sidebar.radio[0].set_value("Carte").run()
        ui.sidebar.slider[0].set_value((70.0, 80.0)).run()
        assert not ui.exception
        assert not ui.get("deck_gl_json_chart")
        assert not [b for b in ui.button if b.key == "recenter_map"]
        assert any("Aucun logement" in item.value for item in ui.info)


def test_width_probe_reports_actual_size_without_rerun_loop(tmp_path):
    node = shutil.which("node")
    if not node:
        pytest.skip("Node indisponible pour tester le composant de mesure")
    script = tmp_path / "probe.mjs"
    script.write_text(MEASURE_JS.replace("export default function", "const render = function") + """
        const assert = (condition) => { if (!condition) throw Error('mesure incorrecte'); };
        let width = 1200, callback, disconnected = false;
        globalThis.ResizeObserver = class {
            constructor(fn) { callback = fn; }
            observe() {}
            disconnect() { disconnected = true; }
        };
        const received = [];
        const cleanup = render({
            parentElement: {querySelector: () => ({getBoundingClientRect: () => ({width})})},
            data: {reported_width: null}, setStateValue: (key, value) => received.push([key, value])
        });
        assert(received.length === 1 && received[0][1] === 1200);
        callback(); await new Promise(r => setTimeout(r, 175));
        assert(received.length === 1);
        width = 360; callback(); await new Promise(r => setTimeout(r, 175));
        assert(received.length === 2 && received[1][1] === 360);
        cleanup(); assert(disconnected);
        const again = render({
            parentElement: {querySelector: () => ({getBoundingClientRect: () => ({width})})},
            data: {reported_width: 360}, setStateValue: (key, value) => received.push([key, value])
        });
        assert(received.length === 2); again();
    """, encoding="utf-8")
    subprocess.run([node, str(script)], check=True, capture_output=True)
