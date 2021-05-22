"""
Author: Yefeng Wang
Data scraping module to retrieve real-time Raydium liquidity pool information.
"""

from stake_layout import STAKE_INFO_LAYOUT_V4, STAKE_INFO_LAYOUT, OPEN_ORDERS_LAYOUT, USER_STAKE_INFO_ACCOUNT_LAYOUT
from resources.ids import STAKE_PROGRAM_ID, STAKE_PROGRAM_ID_V4, STAKE_PROGRAM_ID_V5
from user_types import MemcmpOpts

import asyncio
from ast import literal_eval
from typing import Optional, List

import base58
import base64
import json
import itertools


# Constants
SOLANA_ENDPOINT = "https://api.mainnet-beta.solana.com"
SERUM_ENDPOINT = "https://solana-api.projectserum.com"
RAYDIUM_PRICE_ENDPOINT = "https://api.raydium.io/coin/price"
RAYDIUM_FEE_ENDPOINT = "https://api.raydium.io/pairs"

TOKEN_INFO_FILE = "./resources/tokens.json"
LP_TOKEN_INFO_FILE = "./resources/LPtokens.json"
LP_ADDRESS_INFO_FILE = "./resources/LPtokens_detail_addresses.json"
FARMS_INFO_FILE = "./resources/farms.json"
STAKE_INFO_FILE = "./resources/stake.json"


class SolanaAPICall:
    """
    JSON RPC API call async I/O rewrite.
    """
    def __init__(self, endpoint, session):
        self._endpoint = endpoint
        self._session = session
        self._request_counter = itertools.count()
        self._commitment = None
        self._encoding = None

    def _set_commitment(self, commitment: str):
        if commitment not in ["max", "root", "single", "recent"]:
            raise ValueError("Unsupported commitment type. "
                             "Must be 'max', 'root', 'single' or 'recent'.")
        self._commitment = commitment

    def _set_encoding(self, encoding: str):
        if encoding not in ["base58", "base64", "jsonParsed"]:
            raise ValueError("Unsupported encoding. "
                             "Must be 'base58', 'base64', or 'jsonParsed'.")
        self._encoding = encoding

    def _add_payload(self, method, *params):
        """
        Add JSON RPC header for a request.
        :return:
        """
        request_id = next(self._request_counter) + 1
        headers = {"Content-Type": "application/json"}
        data = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": method,
            "params": params
        }
        return json.dumps(data), headers

    async def _make_request(self, data, headers):
        async with self._session.post(self._endpoint, headers=headers, data=data) as response:
            result = await response.text()
            response.raise_for_status()

        return json.loads(result)

    async def getTokenAccountBalance(self, publicKey: str, commitment: str = 'max'):
        self._set_commitment(commitment)
        payload, header = self._add_payload("getTokenAccountBalance",
                                            publicKey,
                                            {"commitment": self._commitment})
        result = await self._make_request(payload, header)
        return result

    async def getAccountInfo(self, publicKey: str, commitment: str = 'max', encoding: str = 'base64'):
        self._set_commitment(commitment)
        self._set_encoding(encoding)
        payload, header = self._add_payload("getAccountInfo",
                                            publicKey,
                                            {"commitment": self._commitment,
                                             "encoding": self._encoding})
        result = await self._make_request(payload, header)
        return result

    async def getTokenSupply(self, publicKey: str):
        payload, header = self._add_payload("getTokenSupply",
                                            publicKey)
        result = await self._make_request(payload, header)
        return result

    async def getProgramAccounts(self, publicKey: str, commitment: str = 'max', encoding: str = 'base64',
                                 data_size: Optional[int] = None, memcmp_opts: Optional[List[MemcmpOpts]] = None):
        self._set_commitment(commitment)
        self._set_encoding(encoding)
        filters = {"filters": []}
        if memcmp_opts:
            for opt in memcmp_opts:
                filters['filters'].append({"memcmp": dict(opt._asdict())})
        if data_size:
            filters['filters'].append({"dataSize": data_size})
        filters['encoding'] = self._encoding
        filters['commitment'] = self._commitment
        filters = dict(sorted(filters.items())) # make sure the order is correctly sorted aphabetically
        payload, header = self._add_payload("getProgramAccounts",
                                            publicKey,
                                            filters)
        result = await self._make_request(payload, header)
        return result

class RaydiumAPICall:
    def __init__(self, price_endpoint, fee_endpoint, session):
        self._price_endpoint = price_endpoint
        self._fee_endpoint = fee_endpoint
        self._session = session
        self.token_name_dict = self.generate_token_name_dict()

    async def get_price(self):
        """

        :return:
        """
        async with self._session.get(self._price_endpoint) as resp:
            resp.raise_for_status()
            result = await resp.text()

            return literal_eval(result)

    async def get_pair(self):
        async with self._session.get(self._fee_endpoint) as resp:
            resp.raise_for_status()
            result = await resp.text()

            data = literal_eval(result)
            data_dict = {self.token_name_dict[x['name']]: x['apy'] / 100 for x in data}
            return data_dict

    @staticmethod
    def generate_token_name_dict():
        with open(LP_TOKEN_INFO_FILE) as f:
            name_dict = json.load(f)

        return {x: y['symbol'] for x, y in name_dict.items()}

# Pool info

class RaydiumPoolInfo:
    """
    Data Scraper.
    """
    def __init__(self, session):
        self.token_info = self.get_tokens()
        self.LP_token_info = self.get_lp_tokens()
        self.LP_address_info = self.get_details(LP_ADDRESS_INFO_FILE)
        self.farms_info = self.get_details(FARMS_INFO_FILE)
        self.LP_addresses = self.generate_addresses()
        self.SOLANA = SolanaAPICall(SOLANA_ENDPOINT, session)
        self.SERUM = SolanaAPICall(SERUM_ENDPOINT, session)
        self.RAYDIUM = RaydiumAPICall(RAYDIUM_PRICE_ENDPOINT, RAYDIUM_FEE_ENDPOINT, session)

    def base64_decode(self, data, layout):
        data_decode = base64.b64decode(data)
        structured_data = layout.parse(data_decode)
        return structured_data

    def get_tokens(self):
        """
        Read token info from the JSON file.
        :return:
        """
        with open(TOKEN_INFO_FILE) as f:
            return json.load(f)

    def get_token_address(self, token_type: str) -> str:
        """

        :param token_type:
        :return:
        """
        return self.token_info[token_type]['mintAddress']

    def get_token_decimal(self, token_type: str) -> int:
        """

        :param token_type:
        :return:
        """
        return self.token_info[token_type]['decimals']

    def get_lp_tokens(self):
        """
        Read LP token info from the JSON file.
        :return:
        """
        with open(LP_TOKEN_INFO_FILE) as f:
            return json.load(f)

    def get_details(self, file):
        """

        :return:
        """
        with open(file) as f:
            data = json.load(f)

        clean_data = {x['name']: x for x in data}
        return clean_data

    def generate_addresses(self):
        """
        Generate the necessary public key dictionary for retrieving pool composition information.
        :return:
        """
        address_dict = {}
        for pool in self.LP_token_info:
            symbol = self.LP_token_info[pool]['symbol']
            coin, pc = symbol.split('-')
            mint_address = self.LP_token_info[pool]['mintAddress']
            coin_decimals = self.get_token_decimal(coin)
            pc_decimals = self.get_token_decimal(pc)
            lp_decimals = self.LP_token_info[pool]['decimals']

            coin_in_pool_address = self.LP_address_info[symbol]['poolCoinTokenAccount']
            pc_in_pool_address = self.LP_address_info[symbol]['poolPcTokenAccount']

            pool_serum_address = self.LP_address_info[symbol]['ammOpenOrders']

            address_dict[symbol] = {
                "coin": coin,
                "pc": pc,
                "coin_decimals": coin_decimals,
                "pc_decimals": pc_decimals,
                "lp_decimals": lp_decimals,
                "lp_mint_address": mint_address,
                "coin_in_pool_address": coin_in_pool_address,
                "pc_in_pool_address": pc_in_pool_address,
                "pool_amm_address": pool_serum_address
            }
        return address_dict

    async def get_pool_supply(self, lp: str):
        """
        Get the reserves and LP supply from a certain Raydium liquidity pool.
        :param lp: LP name (e.g. OXY-RAY)
        :return:
        """
        # Get coin symbols
        coin = self.LP_addresses[lp]['coin']
        pc = self.LP_addresses[lp]['pc']

        # Get relevant addresses
        amm_address = self.LP_addresses[lp]['pool_amm_address']
        coin_account = self.LP_addresses[lp]['coin_in_pool_address']
        pc_account = self.LP_addresses[lp]['pc_in_pool_address']
        lp_account = self.LP_addresses[lp]['lp_mint_address']

        # Use API to read the data
        coin_amount_data_task = asyncio.create_task(self.SOLANA.getTokenAccountBalance(coin_account))
        pc_amount_data_task = asyncio.create_task(self.SOLANA.getTokenAccountBalance(pc_account))
        lp_supply_task = asyncio.create_task(self.SOLANA.getTokenSupply(lp_account))
        open_order_task = asyncio.create_task(self.SOLANA.getAccountInfo(amm_address))
        price_task = asyncio.create_task(self.RAYDIUM.get_price())


        coin_amount_data = await coin_amount_data_task
        pc_amount_data = await pc_amount_data_task
        lp_supply_data = await lp_supply_task
        open_order_data = await open_order_task
        price = await price_task

        coin_amount = coin_amount_data['result']['value']['uiAmount']
        pc_amount = pc_amount_data['result']['value']['uiAmount']
        lp_supply = lp_supply_data['result']['value']['uiAmount']
        open_order_data_decode = self.base64_decode(open_order_data['result']['value']['data'][0], OPEN_ORDERS_LAYOUT)
        open_order_coin = open_order_data_decode.base_token_total / (10 ** self.LP_addresses[lp]['coin_decimals'])
        open_order_pc = open_order_data_decode.quote_token_total / (10 ** self.LP_addresses[lp]['pc_decimals'])
        coin_price = price[coin]
        pc_price = price[pc]

        total_coin = coin_amount + open_order_coin
        total_pc = pc_amount + open_order_pc

        liquidity = total_coin * coin_price + total_pc * pc_price

        return {
            "coin": self.LP_addresses[lp]['coin'],
            "pc": self.LP_addresses[lp]['pc'],
            "coin_price": coin_price,
            "pc_price": pc_price,
            "coinAmount": total_coin,
            "pcAmount": total_pc,
            "lp_supply": lp_supply,
            "liquidity": liquidity,
            "lp_share_price": liquidity / lp_supply
        }

    async def get_APR(self, farm: str):
        """

        :param farm:
        :return:
        """

        is_fusion = self.farms_info[farm]['fusion']
        is_dual = self.farms_info[farm]['dual']

        farm_lp_info_task = asyncio.create_task(self.get_pool_supply(farm))
        farm_lp_info = await farm_lp_info_task

        # Grab reward per block
        pool_info = self.farms_info[farm]['poolId']

        stake_info_task = asyncio.create_task(self.SOLANA.getAccountInfo(pool_info))
        stake_info = await stake_info_task
        if is_dual:
            # Dual reward
            stake_info_data = self.base64_decode(stake_info['result']['value']['data'][0], STAKE_INFO_LAYOUT_V4)
            per_block_rewardA = stake_info_data.perBlock
            per_block_rewardB = stake_info_data.perBlockB

            rewardA_coin = self.farms_info[farm]['reward']
            rewardB_coin = self.farms_info[farm]['rewardB']

            if rewardA_coin == farm_lp_info['coin']:
                rewardA_price = farm_lp_info['coin_price']
                rewardA_decimal = self.LP_addresses[farm]['coin_decimals']
                rewardB_price = farm_lp_info['pc_price']
                rewardB_decimal = self.LP_addresses[farm]['lp_decimals']
            elif rewardB_coin == farm_lp_info['coin']:
                rewardA_price = farm_lp_info['pc_price']
                rewardA_decimal = self.LP_addresses[farm]['pc_decimals']
                rewardB_price = farm_lp_info['coin_price']
                rewardB_decimal = self.LP_addresses[farm]['coin_decimals']

            stake_lp_pool = self.farms_info[farm]['poolLpTokenAccount']
            staked_lp_amount_task = asyncio.create_task(self.SOLANA.getTokenAccountBalance(stake_lp_pool))
            staked_lp_amount_data = await staked_lp_amount_task
            staked_lp_amount = staked_lp_amount_data['result']['value']['uiAmount']
            staked_liquidity = staked_lp_amount * farm_lp_info['lp_share_price']

            APR_A = per_block_rewardA * 2 * 86400 * 365 * rewardA_price / staked_liquidity / (10 ** rewardA_decimal)
            APR_B = per_block_rewardB * 2 * 86400 * 365 * rewardB_price / staked_liquidity / (10 ** rewardB_decimal)

            farm_lp_info.update({
                rewardA_coin + "_reward_per_block_ann": per_block_rewardA * 2 * 86400 * 365 / (10 ** rewardA_decimal),
                rewardB_coin + "_reward_per_block_ann": per_block_rewardB * 2 * 86400 * 365 / (10 ** rewardB_decimal),
                rewardA_coin + "_APR": APR_A,
                rewardB_coin + "_APR": APR_B
            })

        elif is_fusion:
            # X-USDC fusion pool
            stake_info_data = self.base64_decode(stake_info['result']['value']['data'][0], STAKE_INFO_LAYOUT_V4)
            per_block_reward = stake_info_data.perBlockB
            reward_coin = self.farms_info[farm]['rewardB']

            if reward_coin == farm_lp_info['coin']:
                reward_price = farm_lp_info['coin_price']
                reward_decimal = self.LP_addresses[farm]['coin_decimals']
            else:
                reward_price = farm_lp_info['pc_price']
                reward_decimal = self.LP_addresses[farm]['pc_decimals']

            stake_lp_pool = self.farms_info[farm]['poolLpTokenAccount']
            staked_lp_amount_task = asyncio.create_task(self.SOLANA.getTokenAccountBalance(stake_lp_pool))
            staked_lp_amount_data = await staked_lp_amount_task
            staked_lp_amount = staked_lp_amount_data['result']['value']['uiAmount']
            staked_liquidity = staked_lp_amount * farm_lp_info['lp_share_price']

            APR = per_block_reward * 2 * 86400 * 365 * reward_price / staked_liquidity / (10 ** reward_decimal)

            farm_lp_info.update({
                reward_coin + "_reward_per_block_ann": per_block_reward * 2 * 86400 * 365 / (10 ** reward_decimal),
                reward_coin + "_APR": APR
            })

        else:
            # RAY yield farming pool
            stake_info_data = self.base64_decode(stake_info['result']['value']['data'][0], STAKE_INFO_LAYOUT)

            per_block_reward = stake_info_data.rewardPerBlock
            reward_price = farm_lp_info['coin_price']
            reward_decimal = self.LP_addresses[farm]['coin_decimals']

            stake_lp_pool = self.farms_info[farm]['poolLpTokenAccount']
            staked_lp_amount_task = asyncio.create_task(self.SOLANA.getTokenAccountBalance(stake_lp_pool))
            staked_lp_amount_data = await staked_lp_amount_task
            staked_lp_amount = staked_lp_amount_data['result']['value']['uiAmount']
            staked_liquidity = staked_lp_amount * farm_lp_info['lp_share_price']

            APR = per_block_reward * 2 * 86400 * 365 * reward_price / staked_liquidity / (10 ** reward_decimal)

            farm_lp_info.update({
                "RAY_reward_per_block_ann": per_block_reward * 2 * 86400 * 365 / (10 ** reward_decimal),
                "RAY_APR": APR
            })
        return {farm: farm_lp_info}

    async def get_RAY_staking_dist(self):
        """

        :param program_id:
        :return:
        """
        stake_program_id = STAKE_PROGRAM_ID
        stake_distro_task = asyncio.create_task(self.SOLANA.getProgramAccounts(stake_program_id))
        stake_distro_info = await stake_distro_task

        stake_result = stake_distro_info['result']
        stake_distribution = {
            "publicKey": [],
            "Staked RAY amount": []
        }
        for account_info in stake_result:
            stake_owner_data = self.base64_decode(account_info['account']['data'][0], USER_STAKE_INFO_ACCOUNT_LAYOUT)
            pool_id = base58.b58encode(stake_owner_data.poolId).decode('utf-8')
            owner_account = base58.b58encode(stake_owner_data.stakerOwner).decode('utf-8')
            deposit_balance = stake_owner_data.depositBalance

            if pool_id == "4EwbZo8BZXP5313z5A2H11MRBP15M5n6YxfmkjXESKAW" and deposit_balance > 0:
                # There's only one single-sided staking pool so it's OK to hard-code it
                stake_distribution['publicKey'].append(owner_account)
                stake_distribution['Staked RAY amount'].append(deposit_balance / pow(10, 6))

        return stake_distribution

    async def get_fusion_LP_dist(self, farms: str, program_id: str, LAYOUT):
        """

        :return:
        """
        stake_program_id = program_id
        stake_distro_task = asyncio.create_task(self.SOLANA.getProgramAccounts(stake_program_id))
        stake_distro_info = await stake_distro_task

        stake_result = stake_distro_info['result']
        stake_distribution = {
            "publicKey": [],
            "Staked {} LP amount".format(farms): []
        }
        for account_info in stake_result:
            stake_owner_data = self.base64_decode(account_info['account']['data'][0], LAYOUT)
            pool_id = base58.b58encode(stake_owner_data.poolId).decode('utf-8')
            owner_account = base58.b58encode(stake_owner_data.stakerOwner).decode('utf-8')
            deposit_balance = stake_owner_data.depositBalance

            if pool_id == self.farms_info[farms]['poolId'] and deposit_balance > 0:
                # There's only one single-sided staking pool so it's OK to hard-code it
                stake_distribution["publicKey"].append(owner_account)
                stake_distribution["Staked {} LP amount".format(farms)].append(deposit_balance / pow(10, self.LP_addresses[farms]['lp_decimals']))

        return stake_distribution

    async def get_token_dist(self, mint_address: str):
        """

        :param mint_address:
        :return:
        """

        memcmp = MemcmpOpts(0, mint_address)
        token_distro_task = asyncio.create_task(self.SOLANA.getProgramAccounts("TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA",
                                                                               encoding='jsonParsed',
                                                                               data_size=165,
                                                                               memcmp_opts=[memcmp]))
        token_distro_info = await token_distro_task

        token_distro = {
            "publicKey": [],
            "OwnedAmount": []
        }
        for holder in token_distro_info['result']:
            holder_info = holder['account']['data']['parsed']['info']
            holder_account = holder_info['owner']
            holder_amount = holder_info['tokenAmount']['uiAmount']
            if holder_amount > 0:
                token_distro['publicKey'].append(holder_account)
                token_distro['OwnedAmount'].append(holder_amount)

        return token_distro



