import os
import pathlib
import sys

from app import get_resource_template_and_static_paths


def test_login_artifacts_removed_from_routes_and_factory():
    routes_text = pathlib.Path('app/routes.py').read_text(encoding='utf-8')
    init_text = pathlib.Path('app/__init__.py').read_text(encoding='utf-8')

    assert 'login_required' not in routes_text
    assert 'current_user' not in routes_text
    assert 'LoginManager' not in init_text
    assert 'Bcrypt' not in init_text


def test_get_resource_template_and_static_paths_selects_packaged_layout_when_frozen():
    template_dir, static_dir = get_resource_template_and_static_paths()
    frozen = getattr(sys, 'frozen', False)

    if frozen:
        assert os.path.basename(template_dir) == 'templates'
        assert os.path.basename(static_dir) == 'static'
    else:
        assert os.path.normpath(template_dir).endswith(os.path.normpath('app/templates'))
        assert os.path.normpath(static_dir).endswith(os.path.normpath('app/static'))
