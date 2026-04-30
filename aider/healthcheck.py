from dataclasses import dataclass

from aider.llm import litellm
from aider.repo import ANY_GIT_ERROR


@dataclass
class HealthCheckResult:
    name: str
    status: str
    message: str
    fix: str | None = None


def _check_api_key(main_model):
    missing = list(main_model.missing_keys or [])
    if missing:
        first = missing[0]
        return HealthCheckResult(
            name="API key",
            status="fail",
            message=f"Missing required environment variables: {', '.join(missing)}",
            fix=f"Set credentials, for example: export {first}=<your_key>",
        )

    return HealthCheckResult(
        name="API key",
        status="pass",
        message="Required API credentials detected for active model.",
    )


def _check_model_connectivity(main_model, include_connectivity=True, timeout=20):
    if not include_connectivity:
        return HealthCheckResult(
            name="Model connectivity",
            status="warn",
            message="Skipped connectivity probe (--quick).",
            fix="Run /health without --quick to verify provider reachability.",
        )

    if main_model.missing_keys:
        return HealthCheckResult(
            name="Model connectivity",
            status="fail",
            message="Connectivity probe skipped because required credentials are missing.",
            fix="Set missing API credentials and run /health again.",
        )

    kwargs = dict(main_model.extra_params or {})
    kwargs.setdefault("max_tokens", 1)

    try:
        litellm.completion(
            model=main_model.name,
            messages=[{"role": "user", "content": "healthcheck"}],
            stream=False,
            timeout=timeout,
            **kwargs,
        )
    except Exception as err:
        err_text = str(err).strip().replace("\n", " ")
        if len(err_text) > 200:
            err_text = err_text[:197] + "..."
        return HealthCheckResult(
            name="Model connectivity",
            status="fail",
            message=f"Model/provider probe failed: {err_text}",
            fix="Verify model name, provider routing, network, and API key permissions.",
        )

    return HealthCheckResult(
        name="Model connectivity",
        status="pass",
        message="Provider responded to a minimal model probe.",
    )


def _check_git_readiness(repo):
    if not repo:
        return HealthCheckResult(
            name="Git readiness",
            status="warn",
            message="No git repository detected for current session.",
            fix="Run inside a git repository to enable commit/undo/diff workflows.",
        )

    try:
        dirty = repo.repo.is_dirty()
        try:
            branch = repo.repo.active_branch.name
        except Exception:
            branch = "detached"
    except ANY_GIT_ERROR as err:
        return HealthCheckResult(
            name="Git readiness",
            status="fail",
            message=f"Git state check failed: {err}",
            fix="Verify repository permissions and git configuration.",
        )

    status = "dirty" if dirty else "clean"
    return HealthCheckResult(
        name="Git readiness",
        status="pass",
        message=f"Repository detected ({branch}, {status} working tree).",
    )


def run_health_checks(main_model, repo=None, include_connectivity=True, timeout=20):
    return [
        _check_api_key(main_model),
        _check_model_connectivity(
            main_model,
            include_connectivity=include_connectivity,
            timeout=timeout,
        ),
        _check_git_readiness(repo),
    ]
