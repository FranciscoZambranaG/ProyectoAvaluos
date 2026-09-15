from decimal import Decimal

from app.services.formula_engine import FormulaError, eval_expression


def test_basic_arithmetic():
    assert eval_expression("2 + 3 * 4") == Decimal("14.0000")
    assert eval_expression("(2 + 3) * 4") == Decimal("20.0000")


def test_land_formula_ipiu_ipes_iprt_ipv():
    # 200 m² · ZH1 1384 · IPIU 1.40 · IPES 1.10 · IPRT 1.20 · IPV 1.20 · loc 1 · shape 1
    value = eval_expression(
        "approved_area * zone_m2 * ipiu * ipes * iprt * ipv * location_coef * shape_coef",
        {
            "approved_area": 200,
            "zone_m2": 1384,
            "ipiu": Decimal("1.40"),
            "ipes": Decimal("1.10"),
            "iprt": Decimal("1.20"),
            "ipv": Decimal("1.20"),
            "location_coef": 1,
            "shape_coef": 1,
        },
    )
    assert value == Decimal("613831.6800")


def test_sum_and_unknown_rejected():
    assert eval_expression("1 + SUM(0.20, 0.20)") == Decimal("1.4000")
    try:
        eval_expression("__import__('os').system('x')")
        assert False, "should have raised"
    except FormulaError:
        pass
