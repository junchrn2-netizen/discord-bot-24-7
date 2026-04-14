import discord
from discord.ext import commands, tasks
import os
from dotenv import load_dotenv

load_dotenv()
intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

# ─────────────────────────────────────────────
# 🔰 职级顺序 (精准对齐索引)
# ─────────────────────────────────────────────
RANK_ORDER = [
    "服务领队", "初级管理员", "高级管理员", "主管", "经理",         # 0-4
    "初级公司", "执行实习生", "执行官", "副总裁", "总裁",             # 5-9
    "副主席", "主席", "理事会实习生", "星球委员会", "执行委员会",     # 10-14
    "外星委员会", "领导力实习生", "专员", "社区官员",               # 15-18 (Leadership)
    "社区经理", "副服主", "服主"                                   # 19-21 (Ownership)
]

# ─────────────────────────────────────────────
# 🗂️ 档次划分 (确保社区经理在 Ownership Rank)
# ─────────────────────────────────────────────
RANK_TIERS = [
    {"name": "LR",              "min": 0,  "max": 2,  "is_admin": False},
    {"name": "MR",              "min": 3,  "max": 4,  "is_admin": False},
    {"name": "HR",              "min": 5,  "max": 9,  "is_admin": False},
    {"name": "SHR",             "min": 10, "max": 14, "is_admin": True},
    {"name": "Leadership Rank", "min": 15, "max": 18, "is_admin": True},
    {"name": "Ownership Rank",  "min": 19, "max": 21, "is_admin": True}, # 社区经理从这里开始
]

# 按名字长度降序匹配职位
LONG_MATCH_LIST = sorted(enumerate(RANK_ORDER), key=lambda x: len(x[1]), reverse=True)

# ─────────────────────────────────────────────
# 🔍 核心工具函数
# ─────────────────────────────────────────────

def get_tier_info(index):
    """根据索引返回所属档次字典"""
    for tier in RANK_TIERS:
        if tier["min"] <= index <= tier["max"]:
            return tier
    return None

def get_user_rank_info(member: discord.Member):
    """精准识别成员当前的最高职位索引、职位名以及管理权限"""
    highest_idx = -1
    highest_name = None
    
    for role in member.roles:
        r_name_low = role.name.lower()
        for idx, rank_name in LONG_MATCH_LIST:
            if rank_name.lower() in r_name_low:
                # 排除职位子串冲突
                if rank_name == "总裁" and "副总裁" in r_name_low: continue
                if rank_name == "主席" and "副主席" in r_name_low: continue
                if rank_name == "服主" and "副服主" in r_name_low: continue
                
                if idx > highest_idx:
                    highest_idx = idx
                    highest_name = rank_name
                break # 匹配到一个角色后跳出
                
    tier = get_tier_info(highest_idx)
    is_admin = tier["is_admin"] if tier else False
    
    # 额外检查：是否带有管理层档次关键词作为兜底
    if not is_admin:
        is_admin = any(kw in r.name.upper() for r in member.roles for kw in ["SHR", "LEADERSHIP", "OWNERSHIP"])
        
    return highest_idx, highest_name, is_admin

def find_role_by_keyword(guild: discord.Guild, search_name: str):
    """在服务器中寻找最匹配的身份组"""
    # 1. 完全一致
    for role in guild.roles:
        if role.name == search_name: return role
    # 2. 包含匹配 (处理复杂的身份组名如 [👑] Ownership Rank)
    for role in guild.roles:
        r_name = role.name
        if search_name in r_name:
            # 排除职位冲突
            if search_name in ["总裁", "主席", "服主"] and f"副{search_name}" in r_name:
                continue
            return role
    return None

# ─────────────────────────────────────────────
# 🚀 职级变动核心逻辑
# ─────────────────────────────────────────────

async def process_rank_change(ctx, member: discord.Member, direction: int):
    # 1. 强制刷新成员缓存并检查权限
    member = await ctx.guild.fetch_member(member.id)
    my_idx, _, my_is_admin = get_user_rank_info(ctx.author)
    
    if not my_is_admin:
        return await ctx.send("❌ 你没有权限执行职级变动操作！")

    # 2. 识别目标当前职位
    target_idx, target_name, _ = get_user_rank_info(member)
    if target_idx == -1:
        return await ctx.send(f"❌ 无法识别 **{member.display_name}** 的职级。")

    # 3. 等级高度判定 (必须高等级才能操作低等级)
    if my_idx <= target_idx:
        return await ctx.send(f"❌ 你的职级 ({my_idx}) 必须高于对方 ({target_idx})。")

    # 4. 计算变动后的职位和档次
    new_idx = target_idx + direction
    if new_idx < 0 or new_idx >= len(RANK_ORDER):
        return await ctx.send("❌ 职级已达极限。")

    new_rank_name = RANK_ORDER[new_idx]
    old_tier = get_tier_info(target_idx)
    new_tier = get_tier_info(new_idx)

    # 5. 准备要添加和移除的身份组
    roles_to_add = []
    roles_to_remove = []

    # A. 职位身份组变动
    new_pos_role = find_role_by_keyword(ctx.guild, new_rank_name)
    old_pos_role = find_role_by_keyword(ctx.guild, target_name)
    
    if not new_pos_role:
        return await ctx.send(f"❌ 找不到新职位的身份组: `{new_rank_name}`")
    
    roles_to_add.append(new_pos_role)
    if old_pos_role and old_pos_role in member.roles:
        roles_to_remove.append(old_pos_role)

    # B. 档次身份组变动 (跨越分界线时触发)
    if old_tier["name"] != new_tier["name"]:
        new_tier_role = find_role_by_keyword(ctx.guild, new_tier["name"])
        old_tier_role = find_role_by_keyword(ctx.guild, old_tier["name"])
        
        if new_tier_role:
            roles_to_add.append(new_tier_role)
        if old_tier_role and old_tier_role in member.roles:
            roles_to_remove.append(old_tier_role)

    # 6. 执行变动 (先加后删原子化操作)
    try:
        if roles_to_add:
            await member.add_roles(*roles_to_add, reason=f"职级变动: 执行者 {ctx.author}")
        
        # 加完后删除目标身上存在的旧身份组
        if roles_to_remove:
            await member.remove_roles(*roles_to_remove)

        # 7. 结果输出与日志
        action_text = "晋升" if direction == 1 else "降级"
        tier_msg = f" (档次同步: {old_tier['name']} ➔ {new_tier['name']})" if old_tier["name"] != new_tier["name"] else ""
        
        await ctx.send(f"✅ 已将 {member.mention} 从 **{target_name}** {action_text}为 **{new_rank_name}**{tier_msg}")

        # 发送详细日志
        log_chan = bot.get_channel(1454209918432182404)
        if log_chan:
            embed = discord.Embed(
                title=f"职级变动: {action_text}", 
                color=0x3498db if direction == 1 else 0xe74c3c, 
                timestamp=discord.utils.utcnow()
            )
            embed.add_field(name="操作人", value=ctx.author.display_name, inline=True)
            embed.add_field(name="目标", value=member.display_name, inline=True)
            embed.add_field(name="职位变动", value=f"{target_name} ➔ {new_rank_name}", inline=False)
            if old_tier["name"] != new_tier["name"]:
                embed.add_field(name="档次变动", value=f"{old_tier['name']} ➔ {new_tier['name']}", inline=False)
            await log_chan.send(embed=embed)

    except discord.Forbidden:
        await ctx.send("❌ 机器人权限不足，无法修改该成员的身份组！")
    except Exception as e:
        await ctx.send(f"❌ 发生意外错误: {e}")

# ─────────────────────────────────────────────
# ⌨️ 命令入口
# ─────────────────────────────────────────────

@bot.command(name="promote")
async def promote(ctx, member: discord.Member = None):
    await process_rank_change(ctx, member, 1)

@bot.command(name="demote")
async def demote(ctx, member: discord.Member = None):
    await process_rank_change(ctx, member, -1)

@bot.command(name="myrank")
async def myrank(ctx):
    member = await ctx.guild.fetch_member(ctx.author.id)
    idx, name, admin = get_user_rank_info(member)
    tier = get_tier_info(idx)
    if name:
        tier_name = tier['name'] if tier else '未知'
        await ctx.send(f"你的职位: **{name}**\n档次: **{tier_name}**\n管理权: {'✅' if admin else '❌'}")
    else:
        await ctx.send("无法识别你的职级。")

@bot.event
async def on_ready():
    print(f"✅ 机器人 {bot.user} 已启动")
    print(f"当前划分：社区经理(索引19) 属于 Ownership Rank")

bot.run(os.getenv("DISCORD_BOT_TOKEN"))
