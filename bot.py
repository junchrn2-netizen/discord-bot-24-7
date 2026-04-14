import discord
from discord.ext import commands, tasks
import os
from dotenv import load_dotenv

load_dotenv()
intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

# ─────────────────────────────────────────────
# 🔰 职级与档次配置
# ─────────────────────────────────────────────

RANK_ORDER = [
    "服务领队", "初级管理员", "高级管理员", "主管", "经理",         # 0-4
    "初级公司", "执行实习生", "执行官", "副总裁", "总裁",             # 5-9 (HR)
    "副主席", "主席", "理事会实习生", "星球委员会", "执行委员会",     # 10-14 (SHR)
    "外星委员会", "领导力实习生", "专员", "社区官员",               # 15-18 (Leadership)
    "社区经理", "副服主", "服主"                                   # 19-21 (Ownership)
]

RANK_TIERS = [
    {"name": "LR",              "min": 0,  "max": 2,  "is_admin": False},
    {"name": "MR",              "min": 3,  "max": 4,  "is_admin": False},
    {"name": "HR",              "min": 5,  "max": 9,  "is_admin": False},
    {"name": "SHR",             "min": 10, "max": 14, "is_admin": True},
    {"name": "Leadership Rank", "min": 15, "max": 18, "is_admin": True},
    {"name": "Ownership Rank",  "min": 19, "max": 21, "is_admin": True},
]

LONG_MATCH_LIST = sorted(enumerate(RANK_ORDER), key=lambda x: len(x[1]), reverse=True)

# ─────────────────────────────────────────────
# 🔍 增强版身份组寻找逻辑 (彻底解决 HR/SHR 冲突)
# ─────────────────────────────────────────────

def find_role_strict(guild: discord.Guild, search_name: str):
    """
    带有强力过滤的身份组搜寻逻辑
    """
    search_name_up = search_name.upper()
    
    # 1. 第一优先级：名字完全一致 (忽略大小写)
    for role in guild.roles:
        if role.name.upper() == search_name_up:
            return role

    # 2. 第二优先级：包含匹配，但必须排除干扰
    for role in guild.roles:
        r_name_up = role.name.upper()
        
        if search_name_up in r_name_up:
            # 🌟 核心修复点 A: 找 HR 时，必须排除 SHR
            if search_name_up == "HR" and "SHR" in r_name_up:
                continue
                
            # 🌟 核心修复点 B: 找 总裁/主席/服主 时，排除 副总裁/副主席/副服主
            if search_name_up in ["总裁", "主席", "服主"] and f"副{search_name_up}" in r_name_up:
                continue
                
            return role
    return None

def get_tier_info(index):
    for tier in RANK_TIERS:
        if tier["min"] <= index <= tier["max"]:
            return tier
    return None

def get_user_rank_info(member: discord.Member):
    highest_idx = -1
    highest_name = None
    
    for role in member.roles:
        r_name_low = role.name.lower()
        for idx, rank_name in LONG_MATCH_LIST:
            if rank_name.lower() in r_name_low:
                # 排除职位冲突
                if rank_name == "总裁" and "副总裁" in r_name_low: continue
                if rank_name == "主席" and "副主席" in r_name_low: continue
                if rank_name == "服主" and "副服主" in r_name_low: continue
                
                if idx > highest_idx:
                    highest_idx = idx
                    highest_name = rank_name
                break
                
    tier = get_tier_info(highest_idx)
    is_admin = tier["is_admin"] if tier else False
    
    # 档次保底权限
    if not is_admin:
        is_admin = any(kw in r.name.upper() for r in member.roles for kw in ["SHR", "LEADERSHIP", "OWNERSHIP"])
        
    return highest_idx, highest_name, is_admin

# ─────────────────────────────────────────────
# 🚀 职级变动核心
# ─────────────────────────────────────────────

async def process_rank_change(ctx, member: discord.Member, direction: int):
    member = await ctx.guild.fetch_member(member.id)
    my_idx, _, my_is_admin = get_user_rank_info(ctx.author)
    
    if not my_is_admin:
        return await ctx.send("❌ 你没有权限！")

    target_idx, target_name, _ = get_user_rank_info(member)
    if target_idx == -1:
        return await ctx.send(f"❌ 识别失败，请确保目标拥有正确的职级身份组。")

    if my_idx <= target_idx:
        return await ctx.send(f"❌ 你的职级必须高于对方。")

    new_idx = target_idx + direction
    if new_idx < 0 or new_idx >= len(RANK_ORDER):
        return await ctx.send("❌ 无法进一步变动。")

    new_rank_name = RANK_ORDER[new_idx]
    old_tier = get_tier_info(target_idx)
    new_tier = get_tier_info(new_idx)

    # 准备身份组
    roles_to_add = []
    roles_to_remove = []

    # A. 处理职位身份组
    new_pos_role = find_role_strict(ctx.guild, new_rank_name)
    old_pos_role = find_role_strict(ctx.guild, target_name)
    
    if not new_pos_role:
        return await ctx.send(f"❌ 服务器中找不到身份组: `{new_rank_name}`")
    
    roles_to_add.append(new_pos_role)
    if old_pos_role and old_pos_role in member.roles:
        roles_to_remove.append(old_pos_role)

    # B. 处理档次身份组 (解决 HR/SHR 同步问题)
    if old_tier["name"] != new_tier["name"]:
        new_tier_role = find_role_strict(ctx.guild, new_tier["name"])
        old_tier_role = find_role_strict(ctx.guild, old_tier["name"])
        
        if new_tier_role:
            roles_to_add.append(new_tier_role)
            print(f"准备添加档次组: {new_tier_role.name}") # 后台调试
        if old_tier_role and old_tier_role in member.roles:
            roles_to_remove.append(old_tier_role)
            print(f"准备移除档次组: {old_tier_role.name}") # 后台调试

    try:
        # 🌟 先添加所有新身份 (职位 + 档次)
        if roles_to_add:
            await member.add_roles(*roles_to_add, reason=f"职级变动 - 由 {ctx.author.name} 执行")
        
        # 🌟 后移除所有旧身份 (职位 + 档次)
        if roles_to_remove:
            await member.remove_roles(*roles_to_remove)

        action_text = "晋升" if direction == 1 else "降级"
        await ctx.send(f"✅ 已将 {member.mention} {action_text}为 **{new_rank_name}** ({new_tier['name']})")

        # 日志
        log_chan = bot.get_channel(1454209918432182404)
        if log_chan:
            embed = discord.Embed(title=f"职级{action_text}通知", color=0x3498db, timestamp=discord.utils.utcnow())
            embed.add_field(name="目标", value=member.mention)
            embed.add_field(name="变动", value=f"{target_name} ({old_tier['name']}) \n➔ {new_rank_name} ({new_tier['name']})")
            await log_chan.send(embed=embed)

    except Exception as e:
        await ctx.send(f"❌ 操作失败: {e}")

# ─────────────────────────────────────────────
# ⌨️ 命令入口
# ─────────────────────────────────────────────

@bot.command(name="promote")
async def promote(ctx, member: discord.Member = None):
    await process_rank_change(ctx, member, 1)

@bot.command(name="demote")
async def demote(ctx, member: discord.Member = None):
    await process_rank_change(ctx, member, -1)

@bot.command()
async def myrank(ctx):
    member = await ctx.guild.fetch_member(ctx.author.id)
    idx, name, admin = get_user_rank_info(member)
    tier = get_tier_info(idx)
    if name:
        await ctx.send(f"职位: **{name}** | 档次: **{tier['name']}**")
    else:
        await ctx.send("无法识别职级。")

@bot.event
async def on_ready():
    print(f"✅ {bot.user} 已启动 | HR/SHR 识别增强版已激活")

bot.run(os.getenv("DISCORD_BOT_TOKEN"))
