import discord
from discord.ext import commands, tasks
import os
from dotenv import load_dotenv

load_dotenv()
intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

# ─────────────────────────────────────────────
# 🔰 职级顺序 (职位名)
# ─────────────────────────────────────────────
RANK_ORDER = [
    "服务领队", "初级管理员", "高级管理员", "主管", "经理",         # 0-4
    "初级公司", "执行实习生", "执行官", "副总裁", "总裁",             # 5-9 (HR)
    "副主席", "主席", "理事会实习生", "星球委员会", "执行委员会",     # 10-14 (SHR)
    "外星委员会", "领导力实习生", "专员", "社区官员",               # 15-18 (Leadership)
    "社区经理", "副服主", "服主"                                   # 19-21 (Ownership)
]

# 档次与关键词定义
RANK_TIERS = [
    {"name": "LR", "keywords": ["LR"], "min": 0, "max": 2, "is_admin": False},
    {"name": "MR", "keywords": ["MR"], "min": 3, "max": 4, "is_admin": False},
    {"name": "HR", "keywords": ["HR"], "min": 5, "max": 9, "is_admin": False},
    {"name": "SHR", "keywords": ["SHR"], "min": 10, "max": 14, "is_admin": True},
    {"name": "Leadership Rank", "keywords": ["Leadership"], "min": 15, "max": 18, "is_admin": True},
    {"name": "Ownership Rank", "keywords": ["Ownership"], "min": 19, "max": 21, "is_admin": True},
]

# 按名字长度降序匹配职位词
LONG_MATCH_LIST = sorted(enumerate(RANK_ORDER), key=lambda x: len(x[1]), reverse=True)

# ─────────────────────────────────────────────
# 🔍 强力搜索引擎
# ─────────────────────────────────────────────

def find_role_by_flexible_name(guild, target_name):
    """
    智能搜寻身份组：解决 HR/SHR 冲突，解决 [👑] Ownership 等前缀问题
    """
    target_up = target_name.upper()
    
    # 候选名单
    candidates = []
    
    for role in guild.roles:
        r_name_up = role.name.upper()
        
        # 排除 @everyone
        if role.name == "@everyone": continue
        
        # 核心逻辑：如果我们要找的是 "HR"，必须排除名字里带 "SHR" 的角色
        if target_up == "HR":
            if "HR" in r_name_up and "SHR" not in r_name_up:
                candidates.append(role)
        # 其他情况：包含即可
        elif target_up in r_name_up:
            # 排除职位子串冲突 (总裁/副总裁)
            if target_up in ["总裁", "主席", "服主"] and f"副{target_up}" in r_name_up:
                continue
            candidates.append(role)

    if not candidates:
        return None
    
    # 如果有多个候选者，选择名字长度最接近的那个（防止过度匹配）
    candidates.sort(key=lambda r: abs(len(r.name) - len(target_name)))
    return candidates[0]

def get_user_rank_info(member):
    """识别成员当前的最高职位索引"""
    best_idx = -1
    best_name = None
    
    for role in member.roles:
        r_name_low = role.name.lower()
        for idx, rank_name in LONG_MATCH_LIST:
            if rank_name.lower() in r_name_low:
                # 排除冲突
                if rank_name == "总裁" and "副总裁" in r_name_low: continue
                if rank_name == "主席" and "副主席" in r_name_low: continue
                if rank_name == "服主" and "副服主" in r_name_low: continue
                
                if idx > best_idx:
                    best_idx = idx
                    best_name = rank_name
                break
                
    # 检查是否带有管理层关键词
    is_admin = False
    for role in member.roles:
        r_up = role.name.upper()
        if any(kw in r_up for kw in ["SHR", "LEADERSHIP", "OWNERSHIP"]):
            is_admin = True
    if best_idx >= 10: is_admin = True
        
    return best_idx, best_name, is_admin

def get_tier_by_index(index):
    for tier in RANK_TIERS:
        if tier["min"] <= index <= tier["max"]:
            return tier
    return None

# ─────────────────────────────────────────────
# 🚀 职级变动命令
# ─────────────────────────────────────────────

async def change_rank_logic(ctx, member: discord.Member, direction: int):
    # 1. 强制刷新缓存
    member = await ctx.guild.fetch_member(member.id)
    
    # 2. 权限判定
    my_idx, _, is_admin = get_user_rank_info(ctx.author)
    if not is_admin:
        return await ctx.send("❌ 你没有权限！")

    # 3. 目标职位判定
    target_idx, target_name, _ = get_user_rank_info(member)
    if target_idx == -1:
        return await ctx.send("❌ 无法识别对方职位。")

    if my_idx <= target_idx:
        return await ctx.send("❌ 你的职级必须高于对方。")

    # 4. 计算新职位与档次
    new_idx = target_idx + direction
    if new_idx < 0 or new_idx >= len(RANK_ORDER):
        return await ctx.send("❌ 职级已到头。")

    new_rank_name = RANK_ORDER[new_idx]
    old_tier = get_tier_by_index(target_idx)
    new_tier = get_tier_by_index(new_idx)

    # 5. 准备要更改的角色列表
    add_list = []
    rem_list = []

    # 职位角色
    new_pos_role = find_role_by_flexible_name(ctx.guild, new_rank_name)
    old_pos_role = find_role_by_flexible_name(ctx.guild, target_name)
    
    if new_pos_role: add_list.append(new_pos_role)
    if old_pos_role: rem_list.append(old_pos_role)

    # 🌟 档次角色 (核心修复：如果档次名变了)
    if old_tier["name"] != new_tier["name"]:
        # 注意：这里我们用 tier["name"] 去搜，比如搜 "HR" 或 "SHR"
        new_tier_role = find_role_by_flexible_name(ctx.guild, new_tier["name"])
        old_tier_role = find_role_by_flexible_name(ctx.guild, old_tier["name"])
        
        if new_tier_role: 
            add_list.append(new_tier_role)
            print(f"[DEBUG] 发现新档次组: {new_tier_role.name}")
        if old_tier_role: 
            rem_list.append(old_tier_role)
            print(f"[DEBUG] 发现旧档次组: {old_tier_role.name}")

    # 6. 执行变动
    try:
        # 打印调试信息到控制台，方便你查看机器人到底在干嘛
        print(f"--- 职级操作: {member.display_name} ---")
        print(f"准备添加: {[r.name for r in add_list]}")
        print(f"准备移除: {[r.name for r in rem_list]}")

        # 先执行增加
        if add_list:
            await member.add_roles(*add_list, reason=f"执行者: {ctx.author.name}")
        
        # 成功后再执行移除 (过滤掉成员身上本身就没有的角色)
        final_rem = [r for r in rem_list if r in member.roles]
        if final_rem:
            await member.remove_roles(*final_rem)

        action = "晋升" if direction == 1 else "降级"
        await ctx.send(f"✅ 已将 {member.mention} {action}为 **{new_rank_name}** ({new_tier['name']})")

    except discord.Forbidden:
        await ctx.send("❌ **机器人权限不足！** 请进入服务器设置，将机器人的身份组挪到所有职级（HR, SHR 等）的上方！")
    except Exception as e:
        await ctx.send(f"❌ 出错: {e}")
        print(f"[ERROR] {e}")

@bot.command(name="promote")
async def promote(ctx, member: discord.Member = None):
    await change_rank_logic(ctx, member, 1)

@bot.command(name="demote")
async def demote(ctx, member: discord.Member = None):
    await change_rank_logic(ctx, member, -1)

# ─────────────────────────────────────────────
# 🔍 辅助检查命令 (用来检查机器人能不能看到档次组)
# ─────────────────────────────────────────────
@bot.command(name="check")
async def check(ctx):
    """运行此命令检查机器人是否能正确识别服务器身份组"""
    results = []
    # 检查所有档次
    for tier in RANK_TIERS:
        role = find_role_by_flexible_name(ctx.guild, tier["name"])
        status = f"✅ `{role.name}`" if role else "❌ 未找到"
        results.append(f"档次 **{tier['name']}**: {status}")
    
    # 检查职位匹配是否会误判
    results.append("\n**职位冲突检查:**")
    role_hr = find_role_by_flexible_name(ctx.guild, "HR")
    results.append(f"搜索 'HR' 结果: `{role_hr.name if role_hr else '未找到'}`")
    
    await ctx.send("\n".join(results))

@bot.event
async def on_ready():
    print(f"✅ {bot.user} 已上线。如果操作不成功，请查看此控制台的 [DEBUG] 信息。")

bot.run(os.getenv("DISCORD_BOT_TOKEN"))
