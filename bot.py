import discord
from discord.ext import commands, tasks
import os
from dotenv import load_dotenv

load_dotenv()
intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

# ─────────────────────────────────────────────
# 🔰 职级顺序 (根据你服务器的实际名字精准对齐)
# ─────────────────────────────────────────────
RANK_ORDER = [
    "服务领队", "初级管理员", "高级管理员",                         # 0-2 (LR)
    "主管", "经理",                                             # 3-4 (MR)
    "初级公司", "执行实习生", "执行官", "副总裁", "总裁",             # 5-9 (HR)
    "副主席", "主席", "理事会实习生", "星球委员会", "执行委员会",     # 10-14 (SHR)
    "外星委员会", "领导力实习生", "专员", "社区官员",               # 15-18 (Leadership)
    "社区经理", "副服主", "服主"                                   # 19-21 (Ownership)
]

# 🗂️ 档次关键词 (根据你的 !listroles 结果调整)
RANK_TIERS = [
    {"name": "Low Rank",       "search": "Low Rank",        "min": 0,  "max": 2,  "is_admin": False},
    {"name": "Middle Rank",    "search": "Middle Rank",     "min": 3,  "max": 4,  "is_admin": False},
    {"name": "High Rank",      "search": "High Rank",       "min": 5,  "max": 9,  "is_admin": False},
    {"name": "Super High Rank","search": "Super High Rank",  "min": 10, "max": 14, "is_admin": True},
    {"name": "Leadership Rank","search": "Leadership Rank",   "min": 15, "max": 18, "is_admin": True},
    {"name": "Ownership Rank", "search": "Ownership Rank",    "min": 19, "max": 21, "is_admin": True},
]

# 按名字长度降序匹配职位词
LONG_MATCH_LIST = sorted(enumerate(RANK_ORDER), key=lambda x: len(x[1]), reverse=True)

# ─────────────────────────────────────────────
# 🔍 强力搜索引擎 (针对 High Rank / Super High Rank 隔离优化)
# ─────────────────────────────────────────────

def find_role_strict(guild, search_name):
    """
    专门解决包含关系冲突的搜索函数
    """
    search_up = search_name.upper()
    candidates = []
    
    for role in guild.roles:
        r_name_up = role.name.upper()
        
        # 🌟 核心过滤逻辑：找 High Rank 时排除 Super High Rank
        if search_up == "HIGH RANK":
            if "HIGH RANK" in r_name_up and "SUPER" not in r_name_up:
                return role
        
        # 🌟 找总裁/主席时排除副职
        if search_up in ["总裁", "主席", "服主"]:
            if search_up in r_name_up and f"副{search_up}" not in r_name_up:
                candidates.append(role)
                continue

        # 普通包含匹配
        if search_up in r_name_up:
            candidates.append(role)

    if candidates:
        # 选名字最短的（比如搜“经理”，选“经理 | Manager” 而不是 “社区经理 | ...”）
        candidates.sort(key=lambda r: len(r.name))
        return candidates[0]
    return None

def get_user_rank_info(member):
    best_idx, best_name = -1, None
    for role in member.roles:
        r_name = role.name
        for idx, rank_name in LONG_MATCH_LIST:
            if rank_name in r_name:
                # 排除职位冲突 (如副总裁匹配到总裁)
                if rank_name in ["总裁", "主席", "服主"] and f"副{rank_name}" in r_name:
                    continue
                if idx > best_idx:
                    best_idx, best_name = idx, rank_name
                break
    
    # 管理权限判定 (根据索引或档次关键词)
    is_admin = (best_idx >= 10)
    if not is_admin:
        admin_kws = ["SUPER HIGH RANK", "LEADERSHIP RANK", "OWNERSHIP RANK"]
        is_admin = any(kw in r.name.upper() for r in member.roles for kw in admin_kws)
    return best_idx, best_name, is_admin

# ─────────────────────────────────────────────
# 🚀 职级变动核心
# ─────────────────────────────────────────────

async def change_rank(ctx, member: discord.Member, direction: int):
    member = await ctx.guild.fetch_member(member.id)
    my_idx, _, my_admin = get_user_rank_info(ctx.author)
    if not my_admin: return await ctx.send("❌ 你没有权限！")

    t_idx, t_name, _ = get_user_rank_info(member)
    if t_idx == -1: return await ctx.send("❌ 无法识别对方职位。")
    if my_idx <= t_idx: return await ctx.send("❌ 你只能操作比你等级低的人。")

    new_idx = t_idx + direction
    if new_idx < 0 or new_idx >= len(RANK_ORDER): return await ctx.send("❌ 无法再变更等级。")

    new_rank_name = RANK_ORDER[new_idx]
    
    # 档次判定
    old_tier = next(t for t in RANK_TIERS if t["min"] <= t_idx <= t["max"])
    new_tier = next(t for t in RANK_TIERS if t["min"] <= new_idx <= t["max"])

    add_roles, rem_roles = [], []

    # 1. 职位身份组处理
    new_pos_r = find_role_strict(ctx.guild, new_rank_name)
    old_pos_r = find_role_strict(ctx.guild, t_name)
    if new_pos_r: add_roles.append(new_pos_r)
    if old_pos_r: rem_roles.append(old_pos_r)

    # 2. 档次身份组同步 (关键：跨越 HR/SHR)
    if old_tier["name"] != new_tier["name"]:
        new_tier_r = find_role_strict(ctx.guild, new_tier["search"])
        old_tier_r = find_role_strict(ctx.guild, old_tier["search"])
        if new_tier_r: add_roles.append(new_tier_r)
        if old_tier_r: rem_roles.append(old_tier_r)

    try:
        # 先加后删 (原子化)
        if add_roles: await member.add_roles(*add_roles)
        actual_rem = [r for r in rem_roles if r in member.roles]
        if actual_rem: await member.remove_roles(*actual_rem)
        
        action = "晋升" if direction == 1 else "降级"
        await ctx.send(f"✅ 已将 {member.mention} {action}为 **{new_rank_name}** ({new_tier['name']})")
    except Exception as e:
        await ctx.send(f"❌ 权限不足！请在设置里将机器人的身份组拉到最顶端。")

@bot.command()
async def promote(ctx, member: discord.Member = None): await change_rank(ctx, member, 1)

@bot.command()
async def demote(ctx, member: discord.Member = None): await change_rank(ctx, member, -1)

@bot.command()
async def check(ctx):
    lines = []
    for tier in RANK_TIERS:
        r = find_role_strict(ctx.guild, tier["search"])
        status = f"✅ `{r.name}`" if r else "❌ **未识别**"
        lines.append(f"档次 **{tier['name']}**: {status}")
    await ctx.send("\n".join(lines))

@bot.event
async def on_ready():
    print(f"✅ {bot.user} 已启动。")

bot.run(os.getenv("DISCORD_BOT_TOKEN"))
