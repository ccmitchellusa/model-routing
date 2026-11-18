"""Precedence tests for the reference router. Run: python3 test_activity_router.py"""

from pathlib import Path

from activity_router import (
    ActivityRouter,
    Assignment,
    Constraints,
    InMemoryConfigStore,
    NoProviderConfiguredError,
    ProviderEntry,
    RequiredAssignmentMissingError,
    TenantConfig,
    UnknownActivityError,
    load_capabilities,
)

CAPS = load_capabilities(Path(__file__).with_name("model_capabilities.json"))
TENANT = "tenant-a"


def make_router(config: TenantConfig, platform=None):
    store = InMemoryConfigStore()
    store.put(TENANT, config)
    return ActivityRouter(store, CAPS, platform=platform)


def providers(*names, default=None, assignments=None):
    return TenantConfig(
        providers={n: ProviderEntry(n) for n in names},
        default_provider=default,
        assignments=assignments or {},
    )


def test_user_assignment_wins_over_recommendation():
    cfg = providers(
        "openai",
        "anthropic",
        assignments={"plan_project": Assignment("openai", model="gpt-x")},
    )
    r = make_router(cfg).resolve(TENANT, "plan_project")
    assert (r.provider_type, r.model, r.source) == ("openai", "gpt-x", "user")


def test_recommendation_used_when_no_assignment():
    r = make_router(providers("openai", "anthropic")).resolve(TENANT, "plan_project")
    assert r.source == "recommendation"
    assert r.provider_type == "anthropic"  # ranked first for this activity


def test_changing_default_does_not_move_recommended_lane():
    r_openai = make_router(providers("openai", "anthropic", default="openai")).resolve(
        TENANT, "plan_project"
    )
    r_anthropic = make_router(providers("openai", "anthropic", default="anthropic")).resolve(
        TENANT, "plan_project"
    )
    assert r_openai == r_anthropic and r_openai.source == "recommendation"


def test_default_serves_activity_it_is_capable_of():
    # No curated provider for simple_task is configured, so the capable default serves it.
    r = make_router(providers("anthropic", default="anthropic")).resolve(
        TENANT, "simple_task"
    )
    assert (r.provider_type, r.source) == ("anthropic", "fallback")


def test_default_that_lacks_capability_is_not_used_for_gated_activity():
    cfg = providers("openai", default="openai")
    raises(RequiredAssignmentMissingError, lambda: make_router(cfg).resolve(TENANT, "restricted_content_generation"))


def test_gated_activity_served_by_capable_provider():
    r = make_router(providers("restricted_host", "openai")).resolve(
        TENANT, "restricted_content_generation"
    )
    assert r.provider_type == "restricted_host"


def test_restricted_constraint_routes_only_that_passage():
    router = make_router(providers("restricted_host", "anthropic"))
    restricted = router.resolve(
        TENANT, "long_form_generation", constraints=Constraints(sensitivity="restricted")
    )
    normal = router.resolve(TENANT, "long_form_generation")
    assert restricted.activity_id == "restricted_content_generation"
    assert restricted.provider_type == "restricted_host"
    assert normal.activity_id == "long_form_generation"
    assert normal.provider_type == "anthropic"


def test_gated_activity_never_uses_platform_key():
    class Platform:
        def eligible(self, tenant_id):
            return True

        def capable(self, activity_id):
            return True

    router = make_router(providers("openai"), platform=Platform())
    raises(RequiredAssignmentMissingError, lambda: router.resolve(TENANT, "restricted_content_generation"))


def test_platform_fallback_for_eligible_tenant_is_marked_managed():
    class Platform:
        def eligible(self, tenant_id):
            return True

        def capable(self, activity_id):
            return True

    r = make_router(TenantConfig(), platform=Platform()).resolve(TENANT, "simple_task")
    assert r.managed is True and r.source == "platform"


def test_no_provider_gives_clear_error():
    raises(NoProviderConfiguredError, lambda: make_router(TenantConfig()).resolve(TENANT, "simple_task"))


def test_unknown_activity_rejected():
    raises(UnknownActivityError, lambda: make_router(providers("openai")).resolve(TENANT, "not_an_activity"))


def test_missing_required_reports_gated_activities():
    router = make_router(providers("openai"))
    assert "restricted_content_generation" in router.missing_required(TENANT)
    assert "image_edit" not in router.missing_required(TENANT)  # openai can edit


def test_credentials_never_appear_in_resolution():
    r = make_router(providers("openai")).resolve(TENANT, "simple_task")
    assert r.secret_ref == f"secret://{TENANT}/openai"
    assert "sk-" not in repr(r)


def raises(exc, fn):
    try:
        fn()
    except exc:
        return
    raise AssertionError(f"expected {exc.__name__}")


if __name__ == "__main__":
    import sys

    failures = 0
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print("ok  ", name)
            except Exception as e:  # noqa: BLE001
                failures += 1
                print("FAIL", name, e)
    sys.exit(1 if failures else 0)
