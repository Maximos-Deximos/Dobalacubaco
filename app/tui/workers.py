# Execução de operações bloqueantes sem travar o laço de eventos da TUI.

from __future__ import annotations

from collections.abc import Callable
from typing import Any, TypeVar

from textual.worker import WorkerCancelled, WorkerFailed

T = TypeVar("T")


# Executa uma função síncrona em uma thread e devolve seu resultado.
async def run_blocking(
    owner: Any,
    func: Callable[..., T],
    *args: Any,
    **kwargs: Any,
) -> T:
    worker = owner.run_worker(
        lambda: func(*args, **kwargs),
        thread=True,
        group="blocking",
        exit_on_error=False,
    )

    try:
        return await worker.wait()
    except WorkerFailed as exc:
        cause = exc.__cause__
        if cause is not None:
            raise cause
        raise
    except WorkerCancelled as exc:
        raise RuntimeError("Operação cancelada.") from exc
