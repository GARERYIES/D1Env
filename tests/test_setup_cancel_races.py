import threading

import pytest
from test_setup_manager import manager_at, missing_host, wait_terminal


@pytest.mark.parametrize('stage', ['license', 'native_setup'])
def test_one_cancel_request_completes_when_worker_just_entered_user_wait(tmp_path, monkeypatch, stage):
    host = missing_host()
    if stage == 'native_setup':
        host.update(docker_available=True, docker_error='unknown')
    manager, *_ = manager_at(tmp_path, host=host)
    updated = threading.Event()
    release = threading.Event()
    original = manager._update
    def held(*args, **kwargs):
        value = original(*args, **kwargs)
        if args[1:3] == ('WAITING_USER', stage):
            updated.set()
            assert release.wait(3)
        return value
    monkeypatch.setattr(manager, '_update', held)
    task = manager.prepare('cancel-race-' + stage)
    assert updated.wait(3)
    try:
        accepted = manager.cancel(task['task_id'])
        assert accepted['state'] in {'WAITING_USER', 'CANCELLED'}
    finally:
        release.set()
    assert wait_terminal(manager, task['task_id'], states=('CANCELLED',))['state'] == 'CANCELLED'


def test_cancel_is_passed_to_active_automatic_image_preparation(tmp_path):
    from d1env.setup.models import SetupError
    manager, *_ = manager_at(tmp_path)
    entered, release = threading.Event(), threading.Event()
    predicates = []
    def prepare_image(is_cancelled):
        predicates.append(is_cancelled)
        entered.set()
        assert release.wait(3)
        assert is_cancelled() is True
        raise SetupError('SETUP_CANCELLED', 'cancelled fixture image preparation', 'retry explicitly')
    manager.prepare_image = prepare_image
    task = manager.prepare('cancel-image-step-key')
    assert entered.wait(3)
    manager.cancel(task['task_id'])
    release.set()
    assert wait_terminal(manager, task['task_id'], states=('CANCELLED',))['state'] == 'CANCELLED'
    assert len(predicates) == 1
