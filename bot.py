import discord
from discord.ext import commands
import os
import asyncio
from dotenv import load_dotenv

load_dotenv()
intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

# ─────────────────────────────────────────────
# 🔰 职级 ID 精准绑定 (根据你提供的顺序排列)
# ─────────────────────────────────────────────
RANK_IDS = [
    1428876572064223322, # 0: 服务领队
    1433151035605647413, # 1: 初级管理员
    1474453339969290393, # 2: 高级管理员
    1474453748976849057, # 3: 主管
    1474454248057212939, # 4: 经理
    1474454457428344913, # 5: 初级公司
    1474454651477950536, # 6: 执行实习生
    1478803086737801286, # 7: 执行官
    1474455128915574976, # 8: 副总裁
    1474455312185430097, # 9: 总裁
    1474455618763882725, # 10: 副主席
    1474455834883784837, # 11: 主席
    1474456027821904018, # 12: 理事会实习生
    1474456175129919489, # 13: 星球委员会
    1474456544903958685, # 14: 执行委员会
    1474456713246674996, # 15: 外星委员会
    1474456935800770753, # 16: 领导力实习生
    1474457200478126194, # 17: 专员
    1474457093833490575, # 18: 社区官员
    1474457288881213613, # 19: 社区经理
    1433508635056672808, # 20: 副服主
    1433508180247318632  # 21: 服主
]

# 🗂️ 档次 ID 绑定 (根据你的要求精准对齐)
TIER_CONFIG = [
    {"name": "Low Rank",        "id": 1474457977699434629, "min": 0,  "max": 2},
    {"name": "Middle Rank",     "id": 1474458514721083514, "min": 3,  "max": 4},
    {"name": "High Rank",       "id": 1474458682027937863, "min": 5,  "max": 9},
    {"name": "Super High Rank", "id": 1474458976849629227, "min": 10, "max": 15},
    {"name": "Leadership Rank", "id": 1474459321906626818, "min": 16, "max": 18},
    {"name": "Ownership Rank",  "id": 1474459473920917576, "min": 19, "max": 21},
]

# ─────────────────────────────────────────────
# 🔍 核心工具
# ─────────────────────────────────────────────

def get_rank_index(member):
    """根据 ID 获取最高索引"""
    m_role_ids = [r.id for r in member.roles]
    # 从最高级往低级查，保证结果准确
    for i in range(len(RANK_IDS)-1, -1, -1):
        if RANK_IDS[i] in m_role_ids:
            return i
    return -1

def get_tier_role_id(index):
    for t in TIER_CONFIG:
        if t["min"] <= index <= t["max"]:
            return t["id"], t["name"]
    return None, None

# 操作锁，防止多线程冲突
op_lock = asyncio.Lock()

# ─────────────────────────────────────────────
# 🚀 变动核心处理
# ─────────────────────────────────────────────

async def change_rank(ctx, member, direction):
    if not member: return await ctx.send("❌ 请提到一名成员。")
    
    async with op_lock: # 同一秒内只能处理一个请求
        # 1. 刷新成员数据
        try:
            member = await ctx.guild.fetch_member(member.id)
        except:
            return await ctx.send("❌ 无法获取成员。")

        # 2. 权限校验
        my_idx = get_rank_index(ctx.author)
        if my_idx < 10: # 需要副主席以上权限
            return await ctx.send("❌ 权限不足！需要 SHR 及以上职级。")

        t_idx = get_rank_index(member)
        if t_idx == -1:
            return await ctx.send("❌ 无法识别对方职位。")

        if my_idx <= t_idx:
            return await ctx.send("❌ 你的等级必须高于对方。")

        # 3. 计算新职级
        new_idx = t_idx + direction
        if new_idx < 0 or new_idx >= len(RANK_IDS):
            return await ctx.send("❌ 等级已到极限。")

        # 4. 准备身份组
        old_pos_role = ctx.guild.get_role(RANK_IDS[t_idx])
        new_pos_role = ctx.guild.get_role(RANK_IDS[new_idx])
        
        old_t_id, old_t_name = get_tier_role_id(t_idx)
        new_t_id, new_t_name = get_tier_role_id(new_idx)

        add_list = [new_pos_role]
        rem_list = [old_pos_role]

        # 档次切换逻辑
        if old_t_id != new_t_id:
            old_t_role = ctx.guild.get_role(old_t_id)
            new_t_role = ctx.guild.get_role(new_t_id)
            if new_t_role: add_list.append(new_t_role)
            if old_t_role: rem_list.append(old_t_role)

        # 5. 执行操作
        try:
            # 去除 None 和 已经拥有的角色
            add_list = [r for r in add_list if r and r not in member.roles]
            rem_list = [r for r in rem_list if r and r in member.roles]

            # 先加后删
            if add_list: await member.add_roles(*add_list)
            if rem_list: await member.remove_roles(*rem_list)

            action = "晋升" if direction == 1 else "降级"
            res = f"✅ 已成功将 {member.mention} {action}为 <@&{RANK_IDS[new_idx]}>"
            if old_t_id != new_t_id:
                res += f"\n(档次同步从 `{old_t_name}` 变更为 `{new_t_name}`)"
            
            await ctx.send(res)
            
            # 日志记录 (可选)
            log_channel = bot.get_channel(1454209918432182404)
            if log_channel:
                await log_channel.send(f"📈 **职级变动记录**\n执行者: {ctx.author.display_name}\n目标: {member.display_name}\n变更: <@&{RANK_IDS[t_idx]}> ➔ <@&{RANK_IDS[new_idx]}>")

        except Exception as e:
            await ctx.send(f"❌ 运行失败 (请确保机器人身份组在最顶端): {e}")

# ─────────────────────────────────────────────
# ⌨️ 命令入口
# ─────────────────────────────────────────────

@bot.command()
@commands.cooldown(1, 4, commands.BucketType.user) # 4秒冷却，防止连点
async def promote(ctx, member: discord.Member = None):
    await change_rank(ctx, member, 1)

@bot.command()
@commands.cooldown(1, 4, commands.BucketType.user)
async def demote(ctx, member: discord.Member = None):
    await change_rank(ctx, member, -1)

@bot.event
async def on_ready():
    print(f"✅ {bot.user} 已就绪，ID 绑定功能正常")

bot.run(os.getenv("DISCORD_BOT_TOKEN"))
