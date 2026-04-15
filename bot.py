import discord
from discord.ext import commands, tasks
import os
from dotenv import load_dotenv

load_dotenv()
intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

# ─────────────────────────────────────────────
# 🔰 职级顺序 (根据你提供的信息精准排列)
# ─────────────────────────────────────────────
RANK_ORDER = [
    "服务领队", "初级管理员", "高级管理员",                         # 0-2 (LR)
    "主管", "经理",                                             # 3-4 (MR)
    "初级公司", "执行实习生", "执行官", "副总裁", "总裁",             # 5-9 (HR)
    "副主席", "主席", "理事会实习生", "星球委员会", "执行委员会",     # 10-14 (SHR)
    "外星委员会", "领导力实习生", "专员", "社区官员",               # 15-18 (Leadership)
    "社区经理", "副服主", "服主"                                   # 19-21 (Ownership)
]

# 🗂️ 档次划分 (根据你提供的信息精准对齐)
RANK_TIERS = [
    {"name": "LR", "search": ["LR", "低级", "服务"], "min": 0, "max": 2, "is_admin": False},
    {"name": "MR", "search": ["MR", "中级", "主管"], "min": 3, "max": 4, "is_admin": False},
    {"name": "HR", "search": ["HR", "高级排名", "High Rank", "高级职级"], "min": 5, "max": 9, "is_admin": False},
    {"name": "SHR", "search": ["SHR", "超级高级", "Senior High Rank"], "min": 10, "max": 14, "is_admin": True},
    {"name": "Leadership Rank", "search": ["Leadership", "领导"], "min": 15, "max": 18, "is_admin": True},
    {"name": "Ownership Rank", "search": ["Ownership", "所有"], "min": 19, "max": 21, "is_admin": True},
]

LONG_MATCH_LIST = sorted(enumerate(RANK_ORDER), key=lambda x: len(x[1]), reverse=True)

# ─────────────────────────────────────────────
# 🔍 强力搜索引擎 (针对 HR/SHR 隔离优化)
# ─────────────────────────────────────────────

def find_role_smart(guild, search_keywords):
    """智能搜索：优先精确，其次子串，并处理 HR/SHR 冲突"""
    for kw in search_keywords:
        kw_up = kw.upper()
        candidates = []
        for role in guild.roles:
            r_name_up = role.name.upper()
            
            # 隔离逻辑：搜索 HR 时排除名字里带 SHR 的
            if kw_up == "HR" or kw_up == "HIGH RANK" or kw_up == "高级排名":
                if ("HR" in r_name_up and "SHR" not in r_name_up) or \
                   ("HIGH" in r_name_up and "SENIOR" not in r_name_up) or \
                   ("高级" in r_name_up and "超级" not in r_name_up):
                    candidates.append(role)
            elif kw_up == "SHR":
                if "SHR" in r_name_up or "超级" in r_name_up or "SENIOR" in r_name_up:
                    candidates.append(role)
            else:
                if kw_up in r_name_up:
                    # 排除职位冲突 (总裁/副总裁)
                    if kw_up in ["总裁", "主席", "服主"] and f"副{kw_up}" in r_name_up:
                        continue
                    candidates.append(role)

        if candidates:
            # 返回名字长度最接近关键字的，防止搜"经理"搜到"社区经理"
            candidates.sort(key=lambda r: len(r.name))
            return candidates[0]
    return None

def get_user_rank_info(member):
    best_idx, best_name = -1, None
    for role in member.roles:
        r_name_low = role.name.lower()
        for idx, rank_name in LONG_MATCH_LIST:
            if rank_name.lower() in r_name_low:
                # 排除职位子串冲突
                if rank_name == "总裁" and "副总裁" in r_name_low: continue
                if rank_name == "主席" and "副主席" in r_name_low: continue
                if rank_name == "服主" and "副服主" in r_name_low: continue
                if idx > best_idx:
                    best_idx, best_name = idx, rank_name
                break
    
    is_admin = (best_idx >= 10)
    # 保底：检查是否带有管理层档次关键词
    if not is_admin:
        is_admin = any(kw in r.name.upper() for r in member.roles for kw in ["SHR", "LEADERSHIP", "OWNERSHIP", "所有权", "领导"])
    return best_idx, best_name, is_admin

# ─────────────────────────────────────────────
# 🚀 职级变动核心
# ─────────────────────────────────────────────

async def change_rank(ctx, member: discord.Member, direction: int):
    member = await ctx.guild.fetch_member(member.id)
    my_idx, _, my_admin = get_user_rank_info(ctx.author)
    if not my_admin: return await ctx.send("❌ 你没有权限！")

    t_idx, t_name, _ = get_user_rank_info(member)
    if t_idx == -1: return await ctx.send("❌ 无法识别对方身份组。")
    if my_idx <= t_idx: return await ctx.send("❌ 你的等级必须高于对方。")

    new_idx = t_idx + direction
    if new_idx < 0 or new_idx >= len(RANK_ORDER): return await ctx.send("❌ 职级已达极限。")

    new_rank_name = RANK_ORDER[new_idx]
    
    # 找到变动前后的档次
    old_tier = next(t for t in RANK_TIERS if t["min"] <= t_idx <= t["max"])
    new_tier = next(t for t in RANK_TIERS if t["min"] <= new_idx <= t["max"])

    add_roles, rem_roles = [], []

    # 1. 职位角色
    new_pos_r = find_role_smart(ctx.guild, [new_rank_name])
    old_pos_r = find_role_smart(ctx.guild, [t_name])
    if new_pos_r: add_roles.append(new_pos_r)
    if old_pos_r: rem_roles.append(old_pos_r)

    # 2. 档次角色同步 (关键：解决跨越 HR/SHR 的同步)
    if old_tier["name"] != new_tier["name"]:
        new_tier_role = find_role_smart(ctx.guild, new_tier["search"])
        old_tier_role = find_role_smart(ctx.guild, old_tier["search"])
        
        if new_tier_role: add_roles.append(new_tier_role)
        if old_tier_role and old_tier_role in member.roles:
            rem_roles.append(old_tier_role)

    try:
        # 先加后删 (原子化)
        if add_roles: 
            await member.add_roles(*add_roles, reason=f"职级变更: {ctx.author}")
        if rem_roles:
            # 过滤掉不存在的角色
            actual_rem = [r for r in rem_roles if r in member.roles]
            if actual_rem: await member.remove_roles(*actual_rem)
        
        action = "晋升" if direction == 1 else "降级"
        await ctx.send(f"✅ 已将 {member.mention} {action}为 **{new_rank_name}** ({new_tier['name']})")

    except discord.Forbidden:
        await ctx.send("❌ **机器人权限不足**！请去设置里把机器人的身份组拖到最上面。")
    except Exception as e:
        await ctx.send(f"❌ 运行失败: {e}")

@bot.command()
async def promote(ctx, member: discord.Member = None): await change_rank(ctx, member, 1)

@bot.command()
async def demote(ctx, member: discord.Member = None): await change_rank(ctx, member, -1)

# ─────────────────────────────────────────────
# 🛠️ 诊断与列表工具
# ─────────────────────────────────────────────

@bot.command()
async def listroles(ctx):
    """列出服务器里所有的身份组，方便确认名字"""
    roles = [f"`{r.name}`" for r in ctx.guild.roles if r.name != "@everyone"]
    msg = "**当前服务器身份组列表：**\n" + ", ".join(roles)
    if len(msg) > 2000:
        await ctx.send(msg[:1990] + "...")
    else:
        await ctx.send(msg)

@bot.command()
async def check(ctx):
    """诊断档次身份组识别情况"""
    lines = []
    for tier in RANK_TIERS:
        r = find_role_smart(ctx.guild, tier["search"])
        status = f"✅ `{r.name}`" if r else "❌ **未识别 (请改名或更新搜索关键词)**"
        lines.append(f"档次 **{tier['name']}**: {status}")
    await ctx.send("\n".join(lines))

@bot.event
async def on_ready():
    print(f"✅ {bot.user} 已启动。请在服务器输入 !check 检查识别状态。")

bot.run(os.getenv("DISCORD_BOT_TOKEN"))
