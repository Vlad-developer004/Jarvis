"""Regression test for ui/hud_camera.py::draw_cam_standby.

Production crash (real traceback from settings -> Appearance -> toggling a
sidebar visibility switch -> hud._rebuild_left() -> build_left() ->
_draw_cam_standby()): the fallback width/height calc referenced
`hud._panel_w`, an attribute that was renamed to `_panel_w_left`/
`_panel_w_right` in an earlier per-side panel-width refactor and never
updated here (or in ui/hud_widgets.py's make_hud_btn, fixed alongside this).
AttributeError inside a Tkinter callback doesn't crash the app, but it does
abort the rebuild — the left sidebar toggle silently breaks that camera
placeholder every time it's triggered before the canvas has real geometry.
"""
import pytest

tk = pytest.importorskip('tkinter')


@pytest.fixture
def tk_root():
    try:
        root = tk.Tk()
        root.withdraw()
    except tk.TclError as e:
        pytest.skip(f'no display available: {e}')
    yield root
    root.destroy()


class _FakeHud:
    def __init__(self, canvas):
        self._cam_placeholder = canvas
        self._panel_w_left = 320
        self._F = 'Consolas'

    def _px(self, n):
        return n


def test_draw_cam_standby_uses_panel_w_left_not_missing_panel_w(tk_root):
    from ui.hud_camera import draw_cam_standby

    # A freshly created, never-packed canvas reports winfo_width() == 1,
    # which is < 10 and triggers the fallback-width branch that crashed.
    canvas = tk.Canvas(tk_root, highlightthickness=0)
    hud = _FakeHud(canvas)

    draw_cam_standby(hud)  # must not raise AttributeError: no '_panel_w'

    assert canvas.find_all(), 'expected the standby placeholder to draw something'
