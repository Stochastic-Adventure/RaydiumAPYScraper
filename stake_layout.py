from construct import Bytes, Padding, Int64ul, Int8ul, BytesInteger
from construct import BitsInteger, BitsSwapped, BitStruct, Const, Flag
from construct import Struct

# Fusion Pools Layout
STAKE_INFO_LAYOUT_V4 = Struct(
    "state" / Int64ul,
    "nonce" / Int64ul,
    "poolLpTokenAccount" / Bytes(32),
    "poolRewardTokenAccount" / Bytes(32),
    "totalReward" / Int64ul,
    "perShare" / BytesInteger(16),
    "perBlock" / Int64ul,
    "option" / Int8ul,
    "poolRewardTokenAccountB" / Bytes(32),
    Padding(7),
    "totalRewardB" / Int64ul,
    "perShareB" / BytesInteger(16),
    "perBlockB" / Int64ul,
    "lastBlock" / Int64ul,
    "owner" / Bytes(32)
)

# RAY Yield Farming
STAKE_INFO_LAYOUT = Struct(
    "state" / Int64ul,
    "nonce" / Int64ul,
    "poolLpTokenAccount" / Bytes(32),
    "poolRewardTokenAccount" / Bytes(32),
    "owner" / Bytes(32),
    "feeOwner" / Bytes(32),
    "feeY" / Int64ul,
    "feeX" / Int64ul,
    "totalReward" / Int64ul,
    "rewardPerShareNet" / BytesInteger(16),
    "lastBlock" / Int64ul,
    "rewardPerBlock" / Int64ul
)

# Serum Open Orders Book
ACCOUNT_FLAGS_LAYOUT = BitsSwapped(  # Swap to little endian
    BitStruct(
        "initialized" / Flag,
        "market" / Flag,
        "open_orders" / Flag,
        "request_queue" / Flag,
        "event_queue" / Flag,
        "bids" / Flag,
        "asks" / Flag,
        Const(0, BitsInteger(57)),  # Padding
    )
)

# Serum Open Orders Book
OPEN_ORDERS_LAYOUT = Struct(
    Padding(5),
    "account_flags" / ACCOUNT_FLAGS_LAYOUT,
    "market" / Bytes(32),
    "owner" / Bytes(32),
    "base_token_free" / Int64ul,
    "base_token_total" / Int64ul,
    "quote_token_free" / Int64ul,
    "quote_token_total" / Int64ul,
    "free_slot_bits" / Bytes(16),
    "is_bid_bits" / Bytes(16),
    "orders" / Bytes(16)[128],
    "client_ids" / Int64ul[128],
    "referrer_rebate_accrued" / Int64ul,
    Padding(7),
)

