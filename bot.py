import discord
from discord import app_commands
from discord.ext import commands
import os
import asyncio
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

# ─────────────────────────────────────────────
# 🔰 军事职级 ID 精准序列 (从索引 0 到 20)
# ─────────────────────────────────────────────
RANK_IDS = [
    1428876572064223322, # 0: 新兵
    1433151035605647413, # 1: 列兵
    1474453339969290393, # 2: 下士
    1474453748976849057, # 3: 三级军士长
    1474454248057212939, # 4: 二级军士长
    1474454457428344913, # 5: 一级军士长
    1474454651477950536, # 6: 少尉 (特殊)
    1478803086737801286, # 7: 学员
    1474455128915574976, # 8: 初级军官
    1474455312185430097, # 9: 少尉
    1474455618763882725, # 10: 中尉
    1474455834883784837, # 11: 上尉
    1474456027821904018, # 12: 少校
    1474456175129919489, # 13: 中校
    1474456544903958685, # 14: 上校
    1474456713246674996, # 15: 旅长
    1474456935800770753, # 16: 师长
    1474457200478126194, # 17: 陆军上将
    1474457093833490575, # 18: 军事精英
    1505253473690587147, # 19: 皇家精英
    1474457288881213613  # 20: 秘密精英
]

# 🗂️ 阶级/档次 ID 配置
TIER_CONFIG = [
    {"name": "士兵",       "id": 1505251007297486928, "min": 0,  "max": 2},
    {"name": "毕业生",     "id": 1474458514721083514, "min": 3,  "max": 5},
    {"name": "特殊军衔",   "id": 1474458682027937863, "min": 6,  "max": 7},
    {"name": "初级军官",   "id": 1474458976849629227, "min": 8,  "max": 9},
    {"name": "中级军官",   "id": 1505253862817140803, "min": 10, "max": 11},
    {"name": "高级军官",   "id": 1505254019772186694, "min": 12, "max": 14},
    {"name": "将军",       "id": 1474459321906626818, "min": 15, "max": 17},
    {"name": "精英军官",   "id": 1474459473920917576, "min": 18, "max": 20},
]

# 日志频道
LOG_RANK_CHANGE = 1454209918432182404

# ─────────────────────────────────────────────
# 🤖 逻辑核心
# ─────────────────────────────────────────────

def get_rank_index(member):
    m_role_ids = [r.id for r in member.roles]
    for i in range(len(RANK_IDS)-1, -1, -1):
        if RANK_IDS[i] in m_role_ids: return i
    return -1

def get_tier_info(index):
    for t in TIER_CONFIG:
        if t["min"] <= index <= t["max"]: return t
    return None

class MilitaryBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=discord.Intents.all())

bot = MilitaryBot()
op_lock = asyncio.Lock()

# ─────────────────────────────────────────────
# 🚀 晋升/降级权限判定系统
# ─────────────────────────────────────────────

def check_permission(my_idx, target_idx):
    """
    规则：
    1. 初级(8)到高级军官(14) 只能晋升 士兵和毕业生(0-5)
    2. 将军(15)以上 可以晋升所有比自己低的
    """
    if my_idx < 8: return False, "❌ 你的职级太低，无法执行管理操作。"
    
    # 将军及以上 (15-20)
    if my_idx >= 15:
        if my_idx > target_idx: return True, ""
        return False, "❌ 你不能操作职级高于或等于你的人。"
    
    # 军官阶层 (8-14)
    if 8 <= my_idx <= 14:
        if target_idx <= 5: return True, ""
        return False, "❌ 你仅有权晋升/降级 士兵(Soldier) 和 毕业生(Graduate)。"
    
    return False, "❌ 权限错误。"

# ─────────────────────────────────────────────
# ⚔️ 斜杠命令实现
# ─────────────────────────────────────────────

async def process_military_rank(interaction, member, direction):
    async with op_lock:
        await interaction.response.defer()
        member = await interaction.guild.fetch_member(member.id)
        
        my_idx = get_rank_index(interaction.user)
        t_idx = get_rank_index(member)

        # 1. 权限与合法性校验
        if t_idx == -1: return await interaction.followup.send("❌ 无法识别目标的职级。")
        
        can_proceed, error_msg = check_permission(my_idx, t_idx)
        if not can_proceed: return await interaction.followup.send(error_msg)

        new_idx = t_idx + direction
        if new_idx < 0 or new_idx >= len(RANK_IDS): return await interaction.followup.send("❌ 职级已达极限。")

        # 2. 身份组计算
        old_pos_role = interaction.guild.get_role(RANK_IDS[t_idx])
        new_pos_role = interaction.guild.get_role(RANK_IDS[new_idx])
        
        old_t_cfg = get_tier_info(t_idx)
        new_t_cfg = get_tier_info(new_idx)

        add_list, rem_list = [new_pos_role], [old_pos_role]

        if old_t_cfg and new_t_cfg and old_t_cfg["id"] != new_t_cfg["id"]:
            add_list.append(interaction.guild.get_role(new_t_cfg["id"]))
            rem_list.append(interaction.guild.get_role(old_t_cfg["id"]))

        # 3. 执行
        try:
            await member.add_roles(*[r for r in add_list if r])
            await member.remove_roles(*[r for r in rem_list if r and r in member.roles])

            action = "晋升" if direction == 1 else "降级"
            embed = discord.Embed(title=f"🎖️ 军事职级变动", color=discord.Color.gold() if direction==1 else discord.Color.light_gray(), timestamp=datetime.now())
            embed.add_field(name="目标人员", value=member.mention, inline=True)
            embed.add_field(name="执行军官", value=interaction.user.mention, inline=True)
            embed.add_field(name="职位变动", value=f"<@&{RANK_IDS[t_idx]}> ➔ <@&{RANK_IDS[new_idx]}>", inline=False)
            
            if old_t_cfg["id"] != new_t_cfg["id"]:
                embed.add_field(name="阶级同步", value=f"`{old_t_cfg['name']}` ➔ `{new_t_cfg['name']}`")

            await interaction.followup.send(embed=embed)
            
            # 日志
            log_chan = bot.get_channel(LOG_RANK_CHANGE)
            if log_chan: await log_chan.send(embed=embed)

        except Exception as e:
            await interaction.followup.send(f"❌ 操作失败: {e}")

@bot.tree.command(name="promote", description="晋升成员的军事职级")
async def promote(interaction: discord.Interaction, member: discord.Member):
    await process_military_rank(interaction, member, 1)

@bot.tree.command(name="demote", description="降级成员的军事职级")
async def demote(interaction: discord.Interaction, member: discord.Member):
    await process_military_rank(interaction, member, -1)

# ─────────────────────────────────────────────
# ⚙️ 系统指令
# ─────────────────────────────────────────────

@bot.command()
@commands.is_owner()
async def sync(ctx):
    synced = await bot.tree.sync()
    await ctx.send(f"✅ 已同步 {len(synced)} 个斜杠命令！")

@bot.event
async def on_ready():
    print(f"✅ 军事管理 Bot {bot.user} 已上线。")
    print("输入 !sync 同步命令。")

bot.run(os.getenv("DISCORD_BOT_TOKEN"))
