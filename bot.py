# 军事管理 Bot v5 - 含CD、流放、原因、直接授衔
import discord
from discord import app_commands
from discord.ext import commands
import os
import asyncio
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

# ─────────────────────────────────────────────
# 🛡️ 内务部门 ID
# ─────────────────────────────────────────────
INTERNAL_AFFAIRS_ROLE = 1505175647989923941

# ─────────────────────────────────────────────
# 🕐 每个职级的晋升冷却时间（小时）
# 索引对应 RANK_IDS，值 = 到达该职级后需等待的小时数
# ─────────────────────────────────────────────
PROMOTE_CD_HOURS = [
    0,    # 0: 市民 → 无CD
    3,    # 1: 新兵 → 3小时
    6,    # 2: 列兵 → 6小时
    12,   # 3: 下士 → 12小时
    15,   # 4: 三级军士长 → 15小时
    20,   # 5: 二级军士长 → 20小时
    25,   # 6: 一级军士长 → 25小时
    30,   # 7: 少尉(特殊) → 30小时
    35,   # 8: 学员 → 35小时
    40,   # 9: 初级军官 → 40小时
    45,   # 10: 少尉 → 45小时
    50,   # 11: 中尉 → 50小时
    55,   # 12: 上尉 → 55小时
    60,   # 13: 少校 → 60小时
    65,   # 14: 中校 → 65小时
    70,   # 15: 上校 → 70小时
    75,   # 16: 旅长 → 75小时
    80,   # 17: 师长 → 80小时
    85,   # 18: 陆军上将 → 85小时
    250,  # 19: 军事精英 → 250小时
    500,  # 20: 皇家精英 → 500小时
    350,  # 21: 秘密精英 → 350小时
]

# ─────────────────────────────────────────────
# 🔰 军事职级 ID 精准序列 (从索引 0 到 21)
# ─────────────────────────────────────────────
RANK_IDS = [
    1404135688991015083, # 0: 市民
    1428876572064223322, # 1: 新兵
    1433151035605647413, # 2: 列兵
    1474453339969290393, # 3: 下士
    1474453748976849057, # 4: 三级军士长
    1474454248057212939, # 5: 二级军士长
    1474454457428344913, # 6: 一级军士长
    1474454651477950536, # 7: 少尉 (特殊)
    1478803086737801286, # 8: 学员
    1474455128915574976, # 9: 初级军官
    1474455312185430097, # 10: 少尉
    1474455618763882725, # 11: 中尉
    1474455834883784837, # 12: 上尉
    1474456027821904018, # 13: 少校
    1474456175129919489, # 14: 中校
    1474456544903958685, # 15: 上校
    1474456713246674996, # 16: 旅长
    1474456935800770753, # 17: 师长
    1474457200478126194, # 18: 陆军上将
    1474457093833490575, # 19: 军事精英
    1505253473690587147, # 20: 皇家精英
    1474457288881213613  # 21: 秘密精英
]

# 🗂️ 阶级/档次 ID 配置
TIER_CONFIG = [
    {"name": "士兵",       "id": 1505251007297486928, "min": 1,  "max": 3},
    {"name": "毕业生",     "id": 1474458514721083514, "min": 4,  "max": 6},
    {"name": "特殊军衔",   "id": 1474458682027937863, "min": 7,  "max": 8},
    {"name": "初级军官",   "id": 1474458976849629227, "min": 9,  "max": 10},
    {"name": "中级军官",   "id": 1505253862817140803, "min": 11, "max": 12},
    {"name": "高级军官",   "id": 1505254019772186694, "min": 13, "max": 15},
    {"name": "将军",       "id": 1474459321906626818, "min": 16, "max": 18},
    {"name": "精英军官",   "id": 1474459473920917576, "min": 19, "max": 21},
]

# 职级名称映射（用于 setrank 命令）
RANK_NAMES = {
    "市民": 0, "平民": 0,
    "新兵": 1, "列兵": 2, "下士": 3,
    "三级军士长": 4, "二级军士长": 5, "一级军士长": 6,
    "少尉特殊": 7,
    "学员": 8,
    "初级军官": 9,
    "少尉": 10, "中尉": 11, "上尉": 12,
    "少校": 13, "中校": 14, "上校": 15,
    "旅长": 16, "师长": 17, "陆军上将": 18,
    "军事精英": 19, "皇家精英": 20, "秘密精英": 21,
}

# 日志频道
LOG_RANK_CHANGE = 1454209918432182404

# ─────────────────────────────────────────────
# 🤖 逻辑核心
# ─────────────────────────────────────────────

def get_rank_index(member):
    m_role_ids = [r.id for r in member.roles]
    for i in range(len(RANK_IDS)):
        if RANK_IDS[i] in m_role_ids:
            return i
    return -1

def get_tier_info(index):
    for t in TIER_CONFIG:
        if t["min"] <= index <= t["max"]: return t
    return None

def has_internal_affairs(member):
    return any(r.id == INTERNAL_AFFAIRS_ROLE for r in member.roles)

class MilitaryBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=discord.Intents.all())

bot = MilitaryBot()
op_lock = asyncio.Lock()

# 🕐 晋升时间追踪：{user_id: datetime}
last_promotion = {}

# ─────────────────────────────────────────────
# 🚀 权限判定系统
# ─────────────────────────────────────────────

def check_permission(my_idx, target_idx, is_internal_affairs=False):
    if is_internal_affairs:
        return True, ""
    
    if my_idx < 9: return False, "❌ 你的职级太低，无法执行管理操作。"
    
    if my_idx >= 16:
        if my_idx > target_idx: return True, ""
        return False, "❌ 你不能操作职级高于或等于你的人。"
    
    if 9 <= my_idx <= 15:
        if target_idx <= 6: return True, ""
        return False, "❌ 你仅有权晋升/降级 士兵(Soldier) 和 毕业生(Graduate)。"
    
    return False, "❌ 权限错误。"

# ─────────────────────────────────────────────
# ⚔️ 核心操作函数
# ─────────────────────────────────────────────

async def process_military_rank(ctx_or_interaction, member, direction, reason=None):
    """晋升(+1) 或 降级(-1)"""
    async with op_lock:
        if isinstance(ctx_or_interaction, discord.Interaction):
            interaction = ctx_or_interaction
            await interaction.response.defer()
            invoker = interaction.user
            followup = interaction.followup
        else:
            ctx = ctx_or_interaction
            invoker = ctx.author
            followup = ctx

        member = await ctx_or_interaction.guild.fetch_member(member.id)

        if has_internal_affairs(member):
            return await followup.send("🛡️ 目标人员属于内务部门，不可被操作。")

        invoker_is_ia = has_internal_affairs(invoker)
        my_idx = get_rank_index(invoker)
        t_idx = get_rank_index(member)

        if t_idx == -1:
            return await followup.send("❌ 无法识别目标的职级。")

        # 🕐 晋升CD检查
        if direction == 1:
            now = datetime.now()
            if member.id in last_promotion:
                cd_hours = PROMOTE_CD_HOURS[t_idx]
                elapsed = (now - last_promotion[member.id]).total_seconds() / 3600
                remaining_hours = cd_hours - elapsed
                if remaining_hours > 0:
                    if remaining_hours >= 1:
                        return await followup.send(
                            f"⏳ {member.mention} 还需等待 **{remaining_hours:.1f} 小时**才能晋升！"
                        )
                    else:
                        mins = int(remaining_hours * 60)
                        return await followup.send(
                            f"⏳ {member.mention} 还需等待 **{mins} 分钟**才能晋升！"
                        )

        can_proceed, error_msg = check_permission(my_idx, t_idx, invoker_is_ia)
        if not can_proceed:
            return await followup.send(error_msg)

        new_idx = t_idx + direction
        if new_idx < 0 or new_idx >= len(RANK_IDS):
            return await followup.send("❌ 职级已达极限。")

        await apply_rank_change(ctx_or_interaction, member, invoker, t_idx, new_idx, followup, reason=reason)

async def process_exile(ctx_or_interaction, member, reason=None):
    """流放：直接降回市民"""
    async with op_lock:
        if isinstance(ctx_or_interaction, discord.Interaction):
            interaction = ctx_or_interaction
            await interaction.response.defer()
            invoker = interaction.user
            followup = interaction.followup
        else:
            ctx = ctx_or_interaction
            invoker = ctx.author
            followup = ctx

        member = await ctx_or_interaction.guild.fetch_member(member.id)

        if has_internal_affairs(member):
            return await followup.send("🛡️ 目标人员属于内务部门，不可被流放。")

        invoker_is_ia = has_internal_affairs(invoker)
        my_idx = get_rank_index(invoker)
        t_idx = get_rank_index(member)

        if t_idx == -1:
            return await followup.send("❌ 无法识别目标的职级。")

        if t_idx == 0:
            return await followup.send("❌ 目标已经是市民，无法流放。")

        can_proceed, error_msg = check_permission(my_idx, t_idx, invoker_is_ia)
        if not can_proceed:
            return await followup.send(error_msg)

        await apply_rank_change(ctx_or_interaction, member, invoker, t_idx, 0, followup, is_exile=True, reason=reason)

async def process_setrank(ctx_or_interaction, member, rank_name, reason=None):
    """直接设置军衔（仅内务部门）"""
    async with op_lock:
        if isinstance(ctx_or_interaction, discord.Interaction):
            interaction = ctx_or_interaction
            await interaction.response.defer()
            invoker = interaction.user
            followup = interaction.followup
        else:
            ctx = ctx_or_interaction
            invoker = ctx.author
            followup = ctx

        member = await ctx_or_interaction.guild.fetch_member(member.id)

        if has_internal_affairs(member):
            return await followup.send("🛡️ 目标人员属于内务部门，不可被操作。")

        invoker_is_ia = has_internal_affairs(invoker)

        if not invoker_is_ia:
            return await followup.send("❌ 只有内务部门可以使用此命令。")

        rank_name_lower = rank_name.lower()
        new_idx = None
        for name, idx in RANK_NAMES.items():
            if name.lower() == rank_name_lower:
                new_idx = idx
                break

        if new_idx is None:
            rank_list = "、".join(RANK_NAMES.keys())
            return await followup.send(f"❌ 未知职级。可用职级：{rank_list}")

        t_idx = get_rank_index(member)
        if t_idx == -1:
            return await followup.send("❌ 无法识别目标的职级。")

        if t_idx == new_idx:
            return await followup.send(f"❌ 目标已经是该职级，无需更改。")

        await apply_rank_change(ctx_or_interaction, member, invoker, t_idx, new_idx, followup, is_setrank=True, reason=reason)

async def apply_rank_change(ctx_or_interaction, member, invoker, old_idx, new_idx, followup, is_exile=False, is_setrank=False, reason=None):
    """执行身份组变更"""
    old_pos_role = ctx_or_interaction.guild.get_role(RANK_IDS[old_idx])
    new_pos_role = ctx_or_interaction.guild.get_role(RANK_IDS[new_idx])

    old_t_cfg = get_tier_info(old_idx)
    new_t_cfg = get_tier_info(new_idx)

    add_list, rem_list = [new_pos_role], [old_pos_role]

    if is_exile or is_setrank:
        for i in range(1, len(RANK_IDS)):
            role = ctx_or_interaction.guild.get_role(RANK_IDS[i])
            if role and role in member.roles:
                rem_list.append(role)
        for tier in TIER_CONFIG:
            role = ctx_or_interaction.guild.get_role(tier["id"])
            if role and role in member.roles:
                rem_list.append(role)
    else:
        if old_t_cfg and new_t_cfg and old_t_cfg["id"] != new_t_cfg["id"]:
            add_list.append(ctx_or_interaction.guild.get_role(new_t_cfg["id"]))
            rem_list.append(ctx_or_interaction.guild.get_role(old_t_cfg["id"]))

    if is_setrank and new_t_cfg:
        add_list.append(ctx_or_interaction.guild.get_role(new_t_cfg["id"]))

    try:
        add_list = list(set([r for r in add_list if r]))
        rem_list = list(set([r for r in rem_list if r and r in member.roles]))

        await member.add_roles(*add_list)
        await member.remove_roles(*rem_list)

        # ✅ 记录晋升时间
        now = datetime.now()
        last_promotion[member.id] = now

        if is_exile:
            title = "🚫 流放"
            color = discord.Color.dark_red()
        elif is_setrank:
            title = "📋 军衔授予"
            color = discord.Color.blue()
        else:
            title = "🎖️ 军事职级变动"
            color = discord.Color.gold() if new_idx > old_idx else discord.Color.light_gray()

        embed = discord.Embed(
            title=title,
            color=color,
            timestamp=now
        )
        embed.add_field(name="目标人员", value=member.mention, inline=True)
        embed.add_field(name="执行军官", value=invoker.mention, inline=True)
        embed.add_field(name="职位变动", value=f"<@&{RANK_IDS[old_idx]}> ➔ <@&{RANK_IDS[new_idx]}>", inline=False)

        if not is_exile and old_t_cfg and new_t_cfg and old_t_cfg["id"] != new_t_cfg["id"]:
            embed.add_field(name="阶级同步", value=f"`{old_t_cfg['name']}` ➔ `{new_t_cfg['name']}`")

        if reason:
            embed.add_field(name="原因", value=reason, inline=False)

        # 显示下次晋升CD
        next_cd = PROMOTE_CD_HOURS[new_idx]
        if next_cd > 0 and not is_exile:
            embed.set_footer(text=f"⏳ 下次晋升需等待 {next_cd} 小时")

        await followup.send(embed=embed)

        log_chan = bot.get_channel(LOG_RANK_CHANGE)
        if log_chan:
            await log_chan.send(embed=embed)

    except Exception as e:
        await followup.send(f"❌ 操作失败: {e}")

# ─────────────────────────────────────────────
# 📋 命令注册
# ─────────────────────────────────────────────

# 斜杠命令 - 晋升
@bot.tree.command(name="promote", description="晋升成员的军事职级")
async def promote_slash(interaction: discord.Interaction, member: discord.Member):
    await process_military_rank(interaction, member, 1)

# 斜杠命令 - 降级（含原因）
@bot.tree.command(name="demote", description="降级成员的军事职级")
@app_commands.describe(member="目标成员", reason="降级原因")
async def demote_slash(interaction: discord.Interaction, member: discord.Member, reason: str = None):
    await process_military_rank(interaction, member, -1, reason=reason)

# 斜杠命令 - 流放（含原因）
@bot.tree.command(name="exile", description="流放成员，直接降回市民")
@app_commands.describe(member="目标成员", reason="流放原因")
async def exile_slash(interaction: discord.Interaction, member: discord.Member, reason: str = None):
    await process_exile(interaction, member, reason=reason)

# 斜杠命令 - 直接授衔（含原因）
@bot.tree.command(name="setrank", description="直接授予军衔（仅内务部门可用）")
@app_commands.describe(member="目标成员", rank="职级名称", reason="授予原因")
async def setrank_slash(interaction: discord.Interaction, member: discord.Member, rank: str, reason: str = None):
    await process_setrank(interaction, member, rank, reason=reason)

# 前缀命令 - 晋升
@bot.command(name="promote")
async def promote_prefix(ctx: commands.Context, member: discord.Member):
    await process_military_rank(ctx, member, 1)

# 前缀命令 - 降级（含原因）
@bot.command(name="demote")
async def demote_prefix(ctx: commands.Context, member: discord.Member, *, reason: str = None):
    await process_military_rank(ctx, member, -1, reason=reason)

# 前缀命令 - 流放（含原因）
@bot.command(name="exile")
async def exile_prefix(ctx: commands.Context, member: discord.Member, *, reason: str = None):
    await process_exile(ctx, member, reason=reason)

# 前缀命令 - 直接授衔（含原因）
@bot.command(name="setrank")
async def setrank_prefix(ctx: commands.Context, member: discord.Member, rank_name: str, *, reason: str = None):
    await process_setrank(ctx, member, rank_name, reason=reason)

# ─────────────────────────────────────────────
# ⚙️ 系统指令
# ─────────────────────────────────────────────

@bot.command()
async def sync(ctx):
    synced = await bot.tree.sync()
    await ctx.send(f"✅ 已同步 {len(synced)} 个斜杠命令！")

@bot.event
async def on_ready():
    print(f"✅ 军事管理 Bot {bot.user} 已上线。")
    print("输入 !sync 同步命令。")

bot.run(os.getenv("DISCORD_BOT_TOKEN"))
