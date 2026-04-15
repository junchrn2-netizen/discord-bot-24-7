import discord
from discord.ext import commands, tasks
import os
from dotenv import load_dotenv

load_dotenv()
intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

# ─────────────────────────────────────────────
# 🔰 职级顺序 (职位名 - 严禁改动顺序)
# ─────────────────────────────────────────────
RANK_ORDER = [
    "服务领队", "初级管理员", "高级管理员",                         # 0-2 (Low Rank)
    "主管", "经理",                                             # 3-4 (Middle Rank)
    "初级公司", "执行实习生", "执行官", "副总裁", "总裁",             # 5-9 (High Rank)
    "副主席", "主席", "理事会实习生", "星球委员会", "执行委员会",     # 10-14 (Super High Rank)
    "外星委员会", "领导力实习生", "专员", "社区官员",               # 15-18 (Leadership Rank)
    "社区经理", "副服主", "服主"                                   # 19-21 (Ownership Rank)
]

# 🗂️ 档次配置 (使用全称搜索，解决 LR/MR/SHR 识别混乱)
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
# 🔍 强力搜索引擎 (彻底隔离 High 与 Super High)
# ─────────────────────────────────────────────

def find_role_strict(guild, search_text):
    """
    智能搜索：解决包含冲突、职位冲突、档次名冲突
    """
    s_up = search_text.upper()
    
    # 🌟 1. 档次角色搜索 (全称匹配优先)
    if s_up in ["LOW RANK", "MIDDLE RANK", "HIGH RANK", "SUPER HIGH RANK"]:
        for role in guild.roles:
            r_up = role.name.upper()
            if s_up == "HIGH RANK":
                # 搜 High Rank 时，必须排除 Super
                if "HIGH RANK" in r_up and "SUPER" not in r_up: return role
            else:
                if s_up in r_up: return role

    # 🌟 2. 职位角色搜索
    candidates = []
    for role in guild.roles:
        r_up = role.name.upper()
        if s_up in r_up:
            # 排除总裁/副总裁、主席/副主席冲突
            if s_up in ["总裁", "主席", "服主"] and f"副{s_up}" in role.name:
                continue
            candidates.append(role)
            
    if candidates:
        # 选名字长度最接近的候选者
        candidates.sort(key=lambda r: len(r.name))
        return candidates[0]
    return None

def get_user_rank_info(member):
    """精准识别成员职级索引"""
    highest_idx = -1
    highest_name = None
    
    # 强制重新加载成员数据
    for role in member.roles:
        r_name = role.name
        for idx, rank_name in LONG_MATCH_LIST:
            if rank_name in r_name:
                # 二次校验总裁与副总裁
                if rank_name in ["总裁", "主席", "服主"] and f"副{rank_name}" in r_name:
                    continue
                if idx > highest_idx:
                    highest_idx = idx
                    highest_name = rank_name
                break
                
    # 管理权限判定
    is_admin = False
    if highest_idx >= 10: is_admin = True
    else:
        # 检查是否带有特定档次名
        admin_kws = ["SUPER HIGH RANK", "LEADERSHIP RANK", "OWNERSHIP RANK"]
        if any(kw in r.name.upper() for r in member.roles for kw in admin_kws):
            is_admin = True
            
    return highest_idx, highest_name, is_admin

# ─────────────────────────────────────────────
# 🚀 职级变动核心
# ─────────────────────────────────────────────

async def change_rank(ctx, member: discord.Member, direction: int):
    # 1. 刷新成员状态
    member = await ctx.guild.fetch_member(member.id)
    
    # 2. 权限判定 (操作者)
    my_idx, _, my_admin = get_user_rank_info(ctx.author)
    if not my_admin:
        return await ctx.send("❌ 你没有权限执行职级变动操作！")

    # 3. 目标现状判定
    t_idx, t_name, _ = get_user_rank_info(member)
    if t_idx == -1:
        return await ctx.send(f"❌ 无法识别 {member.display_name} 的职位，请确保他拥有职级角色。")

    if my_idx <= t_idx:
        return await ctx.send(f"❌ 你的等级 ({my_idx}) 必须高于对方 ({t_idx})。")

    # 4. 计算新职级
    new_idx = t_idx + direction
    if new_idx < 0 or new_idx >= len(RANK_ORDER):
        return await ctx.send("❌ 等级已到极限。")

    new_rank_name = RANK_ORDER[new_idx]
    
    # 获取所属档次
    old_tier = next(t for t in RANK_TIERS if t["min"] <= t_idx <= t["max"])
    new_tier = next(t for t in RANK_TIERS if t["min"] <= new_idx <= t["max"])

    # 5. 确定要变动的身份组
    add_list = []
    rem_list = []

    # 职位组
    new_pos_r = find_role_strict(ctx.guild, new_rank_name)
    old_pos_r = find_role_strict(ctx.guild, t_name)
    if new_pos_r: add_list.append(new_pos_r)
    if old_pos_r: rem_list.append(old_pos_r)

    # 档次组变动
    if old_tier["name"] != new_tier["name"]:
        new_tier_r = find_role_strict(ctx.guild, new_tier["search"])
        old_tier_role = find_role_strict(ctx.guild, old_tier["search"])
        if new_tier_role: add_list.append(new_tier_role)
        if old_tier_role: rem_list.append(old_tier_role)

    # 6. 执行变动 (先加后删)
    try:
        # 移除重复项
        add_list = list(set(add_list))
        rem_list = list(set(rem_list))

        if add_list: await member.add_roles(*add_list)
        
        # 实际移除用户身上有的
        to_remove = [r for r in rem_list if r in member.roles]
        if to_remove: await member.remove_roles(*to_remove)

        action = "晋升" if direction == 1 else "降级"
        msg = f"✅ 已将 {member.mention} {action}为 **{new_rank_name}**"
        if old_tier["name"] != new_tier["name"]:
            msg += f"\n(档次同步: `{old_tier['name']}` ➔ `{new_tier['name']}`)"
        
        await ctx.send(msg)

        # 发送日志
        log_chan = bot.get_channel(1454209918432182404)
        if log_chan:
            embed = discord.Embed(title=f"职级{action}", color=0x2ecc71 if direction==1 else 0xe74c3c, timestamp=discord.utils.utcnow())
            embed.add_field(name="目标", value=member.display_name, inline=True)
            embed.add_field(name="变动", value=f"{t_name} ➔ {new_rank_name}", inline=True)
            await log_chan.send(embed=embed)

    except discord.Forbidden:
        await ctx.send("❌ 权限不足！请在服务器设置中将机器人的身份组挪到最顶端。")
    except Exception as e:
        await ctx.send(f"❌ 操作失败: {e}")

@bot.command()
async def promote(ctx, member: discord.Member = None): await change_rank(ctx, member, 1)

@bot.command()
async def demote(ctx, member: discord.Member = None): await change_rank(ctx, member, -1)

# ─────────────────────────────────────────────
# 🛠️ 诊断与启动
# ─────────────────────────────────────────────

@bot.command()
async def check(ctx):
    lines = []
    for tier in RANK_TIERS:
        r = find_role_strict(ctx.guild, tier["search"])
        status = f"✅ `{r.name}`" if r else "❌ **未识别 (请检查名字)**"
        lines.append(f"档次 **{tier['name']}**: {status}")
    await ctx.send("\n".join(lines))

@bot.event
async def on_ready():
    print(f"✅ {bot.user} 已上线。请务必确认旧版本已关闭，防止重复发消息！")

bot.run(os.getenv("DISCORD_BOT_TOKEN"))
