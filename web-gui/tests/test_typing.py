import datetime
import pytest
from decimal import Decimal
from enum import Enum
from bson.decimal128 import Decimal128

from flaskr.typing import Operation, Results, CurrencyConversion


class TestOperationTypeReverse:
    def test_buy_reverses_to_sell(self):
        assert Operation.Type.reverse(Operation.Type.buy) == Operation.Type.sell

    def test_sell_reverses_to_buy(self):
        assert Operation.Type.reverse(Operation.Type.sell) == Operation.Type.buy

    def test_earning_reverses_to_buy(self):
        # Cash from a dividend lands in a deposit, so the mirrored billing op is BUY.
        assert Operation.Type.reverse(Operation.Type.earning) == Operation.Type.buy

    def test_receive_cannot_be_reversed(self):
        with pytest.raises(RuntimeError):
            Operation.Type.reverse(Operation.Type.receive)

    def test_unknown_op_raises(self):
        with pytest.raises(RuntimeError):
            Operation.Type.reverse("NOPE")


class TestAdjustQuantity:
    def test_buy_adds(self):
        assert Operation.adjustQuantity(Operation.Type.buy, 10, 5) == 15

    def test_sell_subtracts(self):
        assert Operation.adjustQuantity(Operation.Type.sell, 10, 3) == 7

    def test_receive_adds(self):
        assert Operation.adjustQuantity(Operation.Type.receive, 10, 5) == 15

    def test_earning_does_not_change_quantity(self):
        # A dividend doesn't change share count on the asset side — this is the
        # asymmetry with adjustBillingQuantity, which subtracts the tax instead.
        assert Operation.adjustQuantity(Operation.Type.earning, 10, 5) == 10

    def test_unknown_op_raises(self):
        with pytest.raises(RuntimeError):
            Operation.adjustQuantity("NOPE", 10, 5)

    @pytest.mark.parametrize("initial,adjustment,expected", [
        (Decimal128("10.5"), Decimal128("0.1"), Decimal("10.6")),
        (Decimal("10.5"), 1, Decimal("11.5")),
        (10, Decimal("0.5"), Decimal("10.5")),
    ])
    def test_mixed_numeric_inputs_normalize(self, initial, adjustment, expected):
        assert Operation.adjustQuantity(Operation.Type.buy, initial, adjustment) == expected


class TestAdjustBillingQuantity:
    # adjustBillingQuantity mirrors adjustQuantity but for the cash flow posted
    # to the billing deposit. The EARNING branch is where it diverges from
    # adjustQuantity — a dividend doesn't change the asset's share count, but
    # the withholding tax provision DOES reduce the cash arriving on the deposit.

    def test_buy_adds_provision(self):
        # BUY $560 with $25 broker commission — deposit pays $585 out.
        assert Operation.adjustBillingQuantity(Operation.Type.buy, 560, 25) == 585

    def test_sell_subtracts_provision(self):
        # SELL $560 with $25 broker commission — deposit receives $535 net.
        assert Operation.adjustBillingQuantity(Operation.Type.sell, 560, 25) == 535

    def test_earning_subtracts_provision(self):
        # The bug from TODO: $100 dividend with $19 withholding tax — deposit
        # must only receive $81, not the full $100. Before the fix this returned
        # 100 because adjustQuantity(EARNING, ...) treats provision as a no-op.
        assert Operation.adjustBillingQuantity(Operation.Type.earning, 100, 19) == 81

    def test_receive_is_not_supported(self):
        # RECEIVE is rejected upstream as unsupported for billing (code 200);
        # the helper should not silently accept it.
        with pytest.raises(RuntimeError):
            Operation.adjustBillingQuantity(Operation.Type.receive, 100, 5)

    def test_unknown_op_raises(self):
        with pytest.raises(RuntimeError):
            Operation.adjustBillingQuantity("NOPE", 100, 5)

    @pytest.mark.parametrize("initial,provision,expected", [
        (Decimal("100.50"), Decimal("19.10"), Decimal("81.40")),
        (Decimal128("100.50"), Decimal128("19.10"), Decimal("81.40")),
        (100, Decimal("19.50"), Decimal("80.50")),
    ])
    def test_earning_handles_decimal_and_decimal128(self, initial, provision, expected):
        # Inputs from Mongo come as Decimal128; inputs from the form parser
        # come as Decimal or int. The helper must normalize both.
        assert Operation.adjustBillingQuantity(Operation.Type.earning, initial, provision) == expected


class TestDisplayString:
    def test_deposit_buy_displays_as_deposit(self):
        assert Operation.displayString(Operation.Type.buy, 'Deposit') == 'DEPOSIT'

    def test_deposit_sell_displays_as_withdraw(self):
        assert Operation.displayString(Operation.Type.sell, 'Deposit') == 'WITHDRAW'

    def test_equity_earning_displays_as_dividend(self):
        assert Operation.displayString(Operation.Type.earning, 'Equity') == 'DIVIDEND'

    def test_deposit_earning_falls_through_to_raw_op(self):
        assert Operation.displayString(Operation.Type.earning, 'Deposit') == 'EARNING'

    def test_equity_buy_falls_through_to_raw_op(self):
        assert Operation.displayString(Operation.Type.buy, 'Equity') == 'BUY'

    def test_unknown_asset_type_falls_through_to_raw_op(self):
        assert Operation.displayString(Operation.Type.sell, 'Crypto') == 'SELL'

    def test_enum_input_is_unwrapped_to_its_value(self):
        # Defensive branch for callers that hand in an Enum instead of a raw
        # string — the function should still dispatch on the underlying value.
        class OpEnum(Enum):
            buy = 'BUY'
        assert Operation.displayString(OpEnum.buy, 'Deposit') == 'DEPOSIT'


class TestResultsTimeranges:
    def test_includes_first_year(self):
        assert str(Results.firstYear) in Results.timeranges()

    def test_includes_current_year(self):
        assert str(datetime.date.today().year) in Results.timeranges()

    def test_length_spans_first_to_current_inclusive(self):
        expected = datetime.date.today().year - Results.firstYear + 1
        assert len(Results.timeranges()) == expected

    def test_values_are_strings(self):
        assert all(isinstance(y, str) for y in Results.timeranges())


class TestCurrencyConversionStaticRate:
    def test_same_currency_is_one(self):
        assert CurrencyConversion.staticRate('USD', 'USD') == Decimal(1)

    def test_gbp_to_gbx(self):
        assert CurrencyConversion.staticRate('GBP', 'GBX') == Decimal(100)

    def test_gbx_to_gbp(self):
        assert CurrencyConversion.staticRate('GBX', 'GBP') == Decimal("0.01")

    def test_unsupported_pair_raises(self):
        with pytest.raises(NotImplementedError):
            CurrencyConversion.staticRate('USD', 'PLN')


class TestCurrencyConversionStaticConvert:
    def test_same_currency_returns_value_unchanged(self):
        assert CurrencyConversion.staticConvert('USD', 'USD', Decimal("12.5")) == Decimal("12.5")

    def test_gbp_to_gbx_multiplies_by_100(self):
        assert CurrencyConversion.staticConvert('GBP', 'GBX', Decimal("1.5")) == Decimal("150")

    def test_gbx_to_gbp_divides_by_100(self):
        assert CurrencyConversion.staticConvert('GBX', 'GBP', Decimal("150")) == Decimal("1.5")

    def test_unsupported_pair_raises(self):
        with pytest.raises(NotImplementedError):
            CurrencyConversion.staticConvert('USD', 'PLN', Decimal("100"))
