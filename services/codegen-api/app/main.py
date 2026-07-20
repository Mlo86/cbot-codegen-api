# Auto-generated patch: ensure StrategySpec is imported to avoid NameError at module load
# Please replace the attempted imports below with the project's canonical import if known.
try:
    from services.codegen_api.models import StrategySpec
except Exception:
    try:
        from codegen_api.models import StrategySpec
    except Exception:
        try:
            from .models import StrategySpec
        except Exception:
            StrategySpec = None

__all__ = ["StrategySpec"]
