import discord
from discord.ext import commands, tasks
import os
from dotenv import load_dotenv

load_dotenv()
intents = discord.Intents.all()
# 强制设定前缀
bot = commands.Bot(command_prefix="!", intents=intents)

# ─────────────────────────────────────────────
# 🔰 职级顺序 (根据你最新的反馈)
# ─────────────────────────────────────────────
RANK_ORDER = [
    "服务领队", "初级管理员", "高级管理员",                         # 0-2 (Low Rank)
    "主管", "经理",                                             # 3-4 (Middle Rank)
    "初级公司", "执行实习生", "执行官", "副总裁", "总裁",             # 5-9 (High Rank)
    "副主席", "主席", "理事会实习生", "星球委员会", "执行委员会", "外星委员会", # 10-15 (Super High Rank)
    "领导力实习生", "专员", "社区官员",                             # 16-18 (Leadership Rank)
    "社区经理", "副服主", "服主"                                   # 19-21 (Ownership Rank)
]

# 🗂️ 档次配置
RANK_TIERS = [
    {"name": "Low Rank",       "search": "Low Rank",        "min": 0,  "max": 2},
    {"name": "Middle Rank",    "search": "Middle Rank",     "min": 3,  "max": 4},
    {"name": "High Rank",      "search": "High Rank",       "min": 5,  "max": 9},
    {"name": "Super High Rank","search": "Super High Rank",  "min": 10, "max": 15},
    {"name": "Leadership Rank","search": "Leadership Rank",   "min": 16, "max": 18},
    {"name": "Ownership Rank", "search": "Ownership Rank",    "min": 19, "max": 21},
]

# 名字长度降序，用于识别
LONG_MATCH_LIST = sorted(enumerate(RANK_ORDER), key=lambda x: len(x[1]), reverse=True)

# ─────────────────────────────────────────────
# 🔍 智能识别
# ─────────────────────────────────────────────

def find_role_strict(guild, search_name):
    s_up = search_name.upper()
    # 针对 High Rank 的特殊隔离
    if s_up == "HIGH RANK":
        for r in guild.roles:
            n = r.name.upper()
            if "HIGH RANK" in n and "SUPER" not in n: return r
    
    # 普通匹配逻辑 (排除副职干扰)
    candidates = []
    for r in guild.roles:
        n = r.name.upper()
        if s_up in n:
            if s_up in ["总裁", "主席", "服主"] and f"副{s_up}" in r.name: continue
            candidates.append(r)
    if candidates:
        candidates.sort(key=lambda r: len(r.name))
        return candidates[0]
    return None

def get_member_rank_info(member):
    best_idx, best_name = -1, None
    for role in member.roles:
        r_n = role.name
        for idx, name in LONG_MATCH_LIST:
            if name in r_n:
                if name in ["总裁", "主席", "服主"] and f"副{name}" in r_n: continue
                if idx > best_idx: best_idx, best_name = idx, name
                break
    
    is_admin = (best_idx >= 10)
    if not is_admin:
        is_admin = any(kw in r.name.upper() for r in member.roles for kw in ["SUPER HIGH RANK", "LEADERSHIP RANK", "OWNERSHIP RANK"])
    return best_idx, best_name, is_admin

# ─────────────────────────────────────────────
# 🚀 核心命令 (增加 3 秒冷却，防止重复触发)
# ─────────────────────────────────────────────

@bot.command()
@commands.has_permissions(manage_roles=True)
@commands.cooldown(1, 3, commands.BucketType.user) # 3秒冷却，防止连点
async def promote(ctx, member: discord.Member = None):
    if not member: return await ctx.send("❌ 请提及一名成员。")
    
    # 强制刷新成员数据
    member = await ctx.guild.fetch_member(member.id)
    my_idx, _, my_admin = get_member_rank_info(ctx.author)
    if not my_admin: return await ctx.send("❌ 权限不足！")

    t_idx, t_name, _ = get_member_rank_info(member)
    if t_idx == -1: return await ctx.send("❌ 无法识别职级角色。")
    if my_idx <= t_idx: return await ctx.send("❌ 等级不足。")
    if t_idx + 1 >= len(RANK_ORDER): return await ctx.send("❌ 已达最高。")

    new_rank = RANK_ORDER[t_idx + 1]
    old_tier = next(t for t in RANK_TIERS if t["min"] <= t_idx <= t["max"])
    new_tier = next(t for t in RANK_TIERS if t["min"] <= (t_idx + 1) <= t["max"])

    add_roles, rem_roles = [], []
    
    # 查找角色对象
    new_pos_r = find_role_strict(ctx.guild, new_rank)
    old_pos_r = find_role_strict(ctx.guild, t_name)
    if not new_pos_r: return await ctx.send(f"❌ 找不到 `{new_rank}` 身份组。")
    
    add_roles.append(new_pos_r)
    if old_pos_r: rem_roles.append(old_pos_r)

    # 档次变动
    if old_tier["name"] != new_tier["name"]:
        ntr = find_role_strict(ctx.guild, new_tier["search"])
        otr = find_role_strict(ctx.guild, old_tier["search"])
        if ntr: add_roles.append(ntr)
        if otr: rem_roles.append(otr)

    try:
        if add_roles: await member.add_roles(*list(set(add_roles)))
        tr = [r for r in rem_roles if r in member.roles]
        if tr: await member.remove_roles(*tr)
        
        msg = f"✅ 已成功将 {member.mention} 晋升为 **{new_rank}**"
        if old_tier["name"] != new_tier["name"]:
            msg += f"\n(档次同步从 `{old_tier['name']}` 变更为 `{new_tier['name']}`)"
        await ctx.send(msg)
    except Exception as e:
        await ctx.send(f"❌ 错误: {e}")

@bot.command()
@commands.has_permissions(manage_roles=True)
@commands.cooldown(1, 3, commands.BucketType.user)
async def demote(ctx, member: discord.Member = None):
    if not member: return
    member = await ctx.guild.fetch_member(member.id)
    my_idx, _, my_admin = get_member_rank_info(ctx.author)
    if not my_admin: return
    
    t_idx, t_name, _ = get_member_rank_info(member)
    if t_idx <= 0: return await ctx.send("❌ 无法降级。")
    if my_idx <= t_idx: return

    new_rank = RANK_ORDER[t_idx - 1]
    old_tier = next(t for t in RANK_TIERS if t["min"] <= t_idx <= t["max"])
    new_tier = next(t for t in RANK_TIERS if t["min"] <= (t_idx - 1) <= t["max"])

    add_roles, rem_roles = [], []
    new_pos_r = find_role_strict(ctx.guild, new_rank)
    old_pos_r = find_role_strict(ctx.guild, t_name)
    if new_pos_r: add_roles.append(new_pos_r)
    if old_pos_r: rem_roles.append(old_pos_r)

    if old_tier["name"] != new_tier["name"]:
        ntr = find_role_strict(ctx.guild, new_tier["search"])
        otr = find_role_strict(ctx.guild, old_tier["search"])
        if ntr: add_roles.append(ntr)
        if otr: rem_roles.append(otr)

    try:
        if add_roles: await member.add_roles(*list(set(add_roles)))
        tr = [r for r in rem_roles if r in member.roles]
        if tr: await member.remove_roles(*tr)
        await ctx.send(f"✅ 已成功将 {member.mention} 降级为 **{new_rank}**")
    except Exception as e:
        await ctx.send(f"❌ 错误: {e}")

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
    print(f"✅ {bot.user} 已启动。如有重复消息，请在控制台输入 pkill -f python。")

bot.run(os.getenv("DISCORD_BOT_TOKEN"))
