import discord
from discord.ext import commands, tasks
import os
from dotenv import load_dotenv

load_dotenv()
intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

# ─────────────────────────────────────────────
# 🔰 职级顺序 (根据你的最新要求：外星委员会 属于 SHR)
# ─────────────────────────────────────────────
RANK_ORDER = [
    "服务领队", "初级管理员", "高级管理员",                         # 0-2 (Low Rank)
    "主管", "经理",                                             # 3-4 (Middle Rank)
    "初级公司", "执行实习生", "执行官", "副总裁", "总裁",             # 5-9 (High Rank)
    "副主席", "主席", "理事会实习生", "星球委员会", "执行委员会", "外星委员会", # 10-15 (Super High Rank)
    "领导力实习生", "专员", "社区官员",                             # 16-18 (Leadership Rank)
    "社区经理", "副服主", "服主"                                   # 19-21 (Ownership Rank)
]

# 🗂️ 档次配置 (精确索引对齐)
RANK_TIERS = [
    {"name": "Low Rank",       "search": "Low Rank",        "min": 0,  "max": 2,  "is_admin": False},
    {"name": "Middle Rank",    "search": "Middle Rank",     "min": 3,  "max": 4,  "is_admin": False},
    {"name": "High Rank",      "search": "High Rank",       "min": 5,  "max": 9,  "is_admin": False},
    {"name": "Super High Rank","search": "Super High Rank",  "min": 10, "max": 15, "is_admin": True},
    {"name": "Leadership Rank","search": "Leadership Rank",   "min": 16, "max": 18, "is_admin": True},
    {"name": "Ownership Rank", "search": "Ownership Rank",    "min": 19, "max": 21, "is_admin": True},
]

# 按名字长度降序匹配，用于职位识别（防止 副主席 识别成 主席）
LONG_MATCH_LIST = sorted(enumerate(RANK_ORDER), key=lambda x: len(x[1]), reverse=True)

# ─────────────────────────────────────────────
# 🔍 智能识别引擎 (解决 HR/SHR 及 总裁/副总裁 冲突)
# ─────────────────────────────────────────────

def find_role_strict(guild, search_name):
    """
    智能搜寻身份组，具备强力冲突过滤。
    """
    s_up = search_name.upper()
    
    # 🌟 A. 档次组特别过滤：找 High Rank 时排除 Super
    if s_up == "HIGH RANK":
        for r in guild.roles:
            n = r.name.upper()
            if "HIGH RANK" in n and "SUPER" not in n: return r
            
    # 🌟 B. 职位组特别过滤：找 总裁/主席/服主 时排除 副总裁/副主席/副服主
    candidates = []
    for r in guild.roles:
        n = r.name.upper()
        if s_up in n:
            # 如果搜 总裁，但名字里有 副总裁，跳过
            if s_up in ["总裁", "主席", "服主"] and f"副{s_up}" in r.name:
                continue
            candidates.append(r)
            
    if candidates:
        # 选名字长度最接近的一个
        candidates.sort(key=lambda r: len(r.name))
        return candidates[0]
    return None

def get_member_rank_info(member):
    """
    返回: (最高索引, 职位名, 是否具有管理权限)
    """
    best_idx = -1
    best_name = None
    
    # 职位识别
    for role in member.roles:
        r_n = role.name
        for idx, name in LONG_MATCH_LIST:
            if name in r_n:
                # 排除 副总裁 对 总裁 的干扰
                if name in ["总裁", "主席", "服主"] and f"副{name}" in r_n: continue
                if idx > best_idx:
                    best_idx, best_name = idx, name
                break
                
    # 权限判定 (SHR 10级 及以上)
    is_admin = (best_idx >= 10)
    if not is_admin:
        # 保底检查档次关键词
        admin_kws = ["SUPER HIGH RANK", "LEADERSHIP RANK", "OWNERSHIP RANK"]
        is_admin = any(kw in r.name.upper() for r in member.roles for kw in admin_kws)
        
    return best_idx, best_name, is_admin

# ─────────────────────────────────────────────
# 🚀 职级变动核心处理
# ─────────────────────────────────────────────

async def change_rank(ctx, member: discord.Member, direction: int):
    # 1. 强制刷新成员数据
    if not member:
        return await ctx.send("❌ 请在命令后 @提到一名成员。")
    try:
        member = await ctx.guild.fetch_member(member.id)
    except:
        return await ctx.send("❌ 无法获取该成员数据。")

    # 2. 权限高度检查
    my_idx, _, my_admin = get_member_rank_info(ctx.author)
    if not my_admin:
        return await ctx.send("❌ 你没有权限执行职级变动！需要 SHR 或更高级别。")

    t_idx, t_name, _ = get_member_rank_info(member)
    if t_idx == -1:
        return await ctx.send(f"❌ 无法识别 **{member.display_name}** 的职位，请确保他有职级身份组。")

    if my_idx <= t_idx:
        return await ctx.send(f"❌ 你的等级索引 ({my_idx}) 必须高于对方 ({t_idx})。")

    # 3. 计算新等级
    new_idx = t_idx + direction
    if new_idx < 0 or new_idx >= len(RANK_ORDER):
        return await ctx.send("❌ 职级已达极限。")

    new_rank_name = RANK_ORDER[new_idx]
    
    # 获取档次配置
    old_tier = next((t for t in RANK_TIERS if t["min"] <= t_idx <= t["max"]), None)
    new_tier = next((t for t in RANK_TIERS if t["min"] <= new_idx <= t["max"]), None)

    # 4. 获取变动身份组
    add_list = []
    rem_list = []

    # A. 职位组
    old_pos_role = find_role_strict(ctx.guild, t_name)
    new_pos_role = find_role_strict(ctx.guild, new_rank_name)
    if not new_pos_role:
        return await ctx.send(f"❌ 错误：搜不到新职位身份组 `{new_rank_name}`。")
    
    add_list.append(new_pos_role)
    if old_pos_role: rem_list.append(old_pos_role)

    # B. 档次组同步 (当跨越分界线时)
    if old_tier["name"] != new_tier["name"]:
        old_tier_role = find_role_strict(ctx.guild, old_tier["search"])
        new_tier_role = find_role_strict(ctx.guild, new_tier["search"])
        if new_tier_role: add_list.append(new_tier_role)
        if old_tier_role: rem_list.append(old_tier_role)

    # 5. 执行变动
    try:
        # 先加后删
        if add_list: await member.add_roles(*add_list)
        
        to_remove = [r for r in rem_list if r in member.roles]
        if to_remove: await member.remove_roles(*to_remove)

        action = "晋升" if direction == 1 else "降级"
        msg = f"✅ 已成功将 {member.mention} **{action}** 为 **{new_rank_name}**"
        if old_tier["name"] != new_tier["name"]:
            msg += f"\n(档次同步从 `{old_tier['name']}` 变更为 `{new_tier['name']}`)"
        await ctx.send(msg)

    except discord.Forbidden:
        await ctx.send("❌ **机器人权限不足**！请进入设置将 `快乐星球机器人` 拖到身份组最上方。")
    except Exception as e:
        await ctx.send(f"❌ 操作失败: {e}")

@bot.command()
async def promote(ctx, member: discord.Member = None): await change_rank(ctx, member, 1)

@bot.command()
async def demote(ctx, member: discord.Member = None): await change_rank(ctx, member, -1)

@bot.command()
async def check(ctx):
    lines = []
    for tier in RANK_TIERS:
        r = find_role_strict(ctx.guild, tier["search"])
        status = f"✅ `{r.name}`" if r else "❌ **未识别 (请检查名字)**"
        lines.append(f"档次 **{tier['name']}**: {status}")
    
    idx, name, _ = get_member_rank_info(ctx.author)
    lines.append(f"\n你的当前职位: **{name}** (索引 {idx})")
    await ctx.send("\n".join(lines))

@bot.event
async def on_ready():
    # 彻底关闭所有重复进程的提示
    print(f"✅ {bot.user} 已启动。如果有重复消息，请重启 Replit 并 pkill python。")

bot.run(os.getenv("DISCORD_BOT_TOKEN"))
