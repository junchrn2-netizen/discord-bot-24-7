import discord
from discord.ext import commands, tasks
import os
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()
('DISCORD_BOT_TOKEN')

# 设置机器人意图
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    """机器人上线时触发"""
    print(f'✅ 机器人已上线: {bot.user}')
    print(f'ID: {bot.user.id}')
    # 设置状态
    await bot.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.watching,
            name="你的服务器"
        ),
        status=discord.Status.online
    )
    # 启动心跳检测
    keep_alive.start()

@tasks.loop(minutes=5)
async def keep_alive():
    """定期心跳，保持连接活跃"""
    print(f'💓 心跳检测: {bot.user}')

@bot.command(name='ping')
async def ping(ctx):
    """简单的ping命令"""
    latency = round(bot.latency * 1000)
    await ctx.send(f'🏓 Pong! 延迟: {latency}ms')

@bot.command(name='status')
async def status(ctx):
    """检查机器人状态"""
    await ctx.send(f'✅ 机器人在线！\n用户: {bot.user}\nID: {bot.user.id}')

@bot.event
async def on_command_error(ctx, error):
    """错误处理"""
    print(f'❌ 命令错误: {error}')
    await ctx.send(f'发生错误: {error}')

def run_bot():
    bot.run('DISCORD_BOT_TOKEN')

if __name__ == '__main__':
    bot.run(os.getenv('DISCORD_BOT_TOKEN')
