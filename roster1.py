import discord
from discord.ext import commands, tasks
import asyncio
import json
import os
import re
from datetime import datetime, timedelta

# Default prefix
DEFAULT_PREFIX = '!'
bot = commands.Bot(command_prefix=DEFAULT_PREFIX, intents=discord.Intents.all())

# Data storage
rosters = {}  # Format: {"gang_name": [{"ign": "Blaze", "discord_ids": [123456789, 987654321]}, ...]}
prefixes = {}  # Format: {"guild_id": "prefix"}
wars = {}  # Format: {"channel_id": {"gang": "royalty", "statuses": {"ign": {...}}, "message_id": 123}}

def save_data():
    with open('roster_data.json', 'w') as f:
        json.dump({'rosters': rosters, 'prefixes': prefixes, 'wars': wars}, f, indent=2)

def load_data():
    global rosters, prefixes, wars
    if os.path.exists('roster_data.json'):
        try:
            with open('roster_data.json', 'r') as f:
                data = json.load(f)
                rosters = data.get('rosters', {})
                prefixes = data.get('prefixes', {})
                wars = data.get('wars', {})
        except:
            rosters = {}
            prefixes = {}
            wars = {}

load_data()

async def get_prefix(bot, message):
    """Get custom prefix for each guild"""
    if not message.guild:
        return DEFAULT_PREFIX
    return prefixes.get(message.guild.id, DEFAULT_PREFIX)

bot.command_prefix = get_prefix

def parse_members(members_text):
    """Parse member text: 'ign @mention, ign2 @mention2 @mention3, ign3 @mention3'"""
    members = []
    parts = members_text.split(',')
    
    for part in parts:
        part = part.strip()
        if not part:
            continue
        
        mention_matches = re.findall(r'<@!?(\d+)>', part)
        discord_ids = [int(mid) for mid in mention_matches]
        ign = re.sub(r'<@!?\d+>', '', part).strip()
        
        if ign:
            members.append({'ign': ign, 'discord_ids': discord_ids})
        elif discord_ids:
            members.append({'ign': f"User_{discord_ids[0]}", 'discord_ids': discord_ids})
    
    return members

def format_roster(gang_name):
    """Format roster for display"""
    if gang_name not in rosters or not rosters[gang_name]:
        return f"**{gang_name.upper()}** - No members"
    
    members = rosters[gang_name]
    output = f"**{gang_name.upper()}** ({len(members)} members)\n"
    output += "-" * 50 + "\n"
    
    for i, member in enumerate(members, 1):
        ign = member['ign']
        discord_ids = member.get('discord_ids', [])
        
        if discord_ids:
            mentions = ', '.join([f"<@{did}>" for did in discord_ids])
            output += f"{i}. **{ign}** - {mentions}\n"
        else:
            output += f"{i}. **{ign}** - No Discord\n"
    
    return output

def parse_status(status_text):
    """Parse status: 00f 123 or 011 456 or 0 0 f 1 2 3"""
    status_text = status_text.strip().lower()
    
    # Check for ZZZ (sleep mode)
    zzz = status_text.endswith('zzz')
    if zzz:
        status_text = status_text[:-3].strip()
    
    parts = status_text.split()
    
    # Handle format like "00f 123" (3 chars then 3 chars)
    if len(parts) == 2 and len(parts[0]) == 3 and len(parts[1]) == 3:
        xyz = parts[0]
        cars = parts[1]
        
        available = xyz[0]
        healing = xyz[1]
        heals = xyz[2]
        
        car1 = int(cars[0]) if cars[0].isdigit() and 1 <= int(cars[0]) <= 6 else None
        car2 = int(cars[1]) if cars[1].isdigit() and 1 <= int(cars[1]) <= 6 else None
        car3 = int(cars[2]) if cars[2].isdigit() and 1 <= int(cars[2]) <= 6 else None
        
    # Handle format like "0 0 f 1 2 3" (space separated)
    elif len(parts) >= 6:
        available = parts[0]
        healing = parts[1]
        heals = parts[2]
        car1 = int(parts[3]) if parts[3].isdigit() and 1 <= int(parts[3]) <= 6 else None
        car2 = int(parts[4]) if parts[4].isdigit() and 1 <= int(parts[4]) <= 6 else None
        car3 = int(parts[5]) if parts[5].isdigit() and 1 <= int(parts[5]) <= 6 else None
    else:
        return None
    
    return {
        'available': available,
        'healing': healing,
        'heals': heals,
        'car1': car1,
        'car2': car2,
        'car3': car3,
        'zzz': zzz
    }

def generate_war_table(channel_id):
    """Generate war status table for a channel"""
    if channel_id not in wars:
        return None
    
    war_data = wars[channel_id]
    gang_name = war_data['gang']
    statuses = war_data.get('statuses', {})
    
    if gang_name not in rosters:
        return f"**⚠️ Gang '{gang_name}' not found in roster!**"
    
    # Get all members from roster
    roster_members = {member['ign'].lower(): member for member in rosters[gang_name]}
    
    # Build table
    table = f"```\n⚔️ WAR STATUS - {gang_name.upper()} ⚔️\n"
    table += f"Updated: {datetime.now().strftime('%H:%M:%S')}\n"
    table += "=" * 70 + "\n"
    table += f"{'IGN':<15} {'Avail':<6} {'Heal':<6} {'Heals':<6} {'C1':<4} {'C2':<4} {'C3':<4} {'😴':<3}\n"
    table += "-" * 70 + "\n"
    
    for ign_lower, member in roster_members.items():
        ign = member['ign']
        status = statuses.get(ign_lower, {})
        
        available = status.get('available', '-')
        healing = status.get('healing', '-')
        heals = status.get('heals', '-')
        car1 = status.get('car1', '-') if status.get('car1') else '-'
        car2 = status.get('car2', '-') if status.get('car2') else '-'
        car3 = status.get('car3', '-') if status.get('car3') else '-'
        zzz = '😴' if status.get('zzz', False) else ''
        
        table += f"{ign:<15} {str(available):<6} {str(healing):<6} {str(heals):<6} {str(car1):<4} {str(car2):<4} {str(car3):<4} {zzz:<3}\n"
    
    table += "=" * 70 + "\n"
    
    # Calculate stats
    total_available = 0
    total_healing = 0
    for status in statuses.values():
        if str(status.get('available', '')).isdigit():
            total_available += int(status['available'])
        if str(status.get('healing', '')).isdigit():
            total_healing += int(status['healing'])
    
    table += f"Total Available: {total_available} | Total Healing: {total_healing}\n"
    table += f"Reported: {len(statuses)}/{len(roster_members)} members\n"
    table += "```"
    
    return table

async def update_war_table(channel):
    """Update war table in a channel"""
    if channel.id not in wars:
        return
    
    table = generate_war_table(channel.id)
    if not table:
        return
    
    message_id = wars[channel.id].get('message_id')
    
    if message_id:
        try:
            msg = await channel.fetch_message(message_id)
            await msg.edit(content=table)
            return
        except:
            pass
    
    # Delete old bot messages
    async for msg in channel.history(limit=50):
        if msg.author == bot.user and msg.id != message_id:
            try:
                await msg.delete()
            except:
                pass
    
    # Send new table
    new_msg = await channel.send(table)
    wars[channel.id]['message_id'] = new_msg.id
    save_data()

@bot.event
async def on_ready():
    print(f'\n{"="*50}')
    print(f'✅ Gang Roster & War Bot is online!')
    print(f'Bot: {bot.user}')
    print(f'Gangs loaded: {len(rosters)}')
    print(f'Active wars: {len(wars)}')
    print(f'{"="*50}\n')
    
    # Restore war tables
    for channel_id in wars:
        channel = bot.get_channel(channel_id)
        if channel:
            await update_war_table(channel)

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return
    
    # Check if this channel has an active war
    if message.channel.id in wars:
        # Get current prefix
        current_prefix = prefixes.get(message.guild.id, DEFAULT_PREFIX)
        
        # Handle commands
        if message.content.startswith(tuple(prefixes.values()) + (DEFAULT_PREFIX,)):
            await bot.process_commands(message)
            return
        
        # Parse as status update
        status = parse_status(message.content)
        if status:
            # Find which IGN this Discord is linked to in this gang
            gang_name = wars[message.channel.id]['gang']
            if gang_name in rosters:
                discord_id = message.author.id
                found_ign = None
                
                for member in rosters[gang_name]:
                    if discord_id in member.get('discord_ids', []):
                        found_ign = member['ign'].lower()
                        break
                
                if found_ign:
                    # Update status
                    if 'statuses' not in wars[message.channel.id]:
                        wars[message.channel.id]['statuses'] = {}
                    
                    wars[message.channel.id]['statuses'][found_ign] = status
                    save_data()
                    
                    # Update table
                    await update_war_table(message.channel)
                    
                    # Confirm
                    confirm = await message.channel.send(f"✅ {found_ign} updated")
                    await asyncio.sleep(2)
                    await confirm.delete()
                else:
                    error = await message.channel.send(f"❌ Your Discord isn't linked to any IGN in **{gang_name}**")
                    await asyncio.sleep(3)
                    await error.delete()
            
            await message.delete()
        else:
            error = await message.channel.send(f"❌ Invalid status format. Use: `00f 123` or `0 0 f 1 2 3`")
            await asyncio.sleep(3)
            await error.delete()
            await message.delete()
    else:
        await bot.process_commands(message)

# ============= WAR COMMANDS =============

@bot.command(name='warstart')
@commands.has_permissions(administrator=True)
async def war_start(ctx, gang: str):
    """Start a war status table for a gang in this channel
    Usage: !warstart gangname"""
    
    gang = gang.lower()
    
    if gang not in rosters:
        await ctx.send(f"❌ Gang **{gang}** doesn't exist! Create it with `!rostercreate {gang}` first.")
        await ctx.message.delete()
        return
    
    if ctx.channel.id in wars:
        await ctx.send(f"❌ A war is already active in this channel! Use `!warend` first.")
        await ctx.message.delete()
        return
    
    # Create new war
    wars[ctx.channel.id] = {
        'gang': gang,
        'statuses': {},
        'message_id': None,
        'started_at': datetime.now().isoformat()
    }
    save_data()
    
    await update_war_table(ctx.channel)
    await ctx.send(f"⚔️ **WAR STARTED for {gang.upper()}!** ⚔️\nMembers can now post their status using: `00f 123` or `0 0 f 1 2 3`")
    await asyncio.sleep(5)
    await ctx.message.delete()

@bot.command(name='warend')
@commands.has_permissions(administrator=True)
async def war_end(ctx):
    """End the war and clear the status table in this channel
    Usage: !warend"""
    
    if ctx.channel.id not in wars:
        await ctx.send(f"❌ No active war in this channel! Use `!warstart gangname` to start one.")
        await ctx.message.delete()
        return
    
    # Delete war table message
    message_id = wars[ctx.channel.id].get('message_id')
    if message_id:
        try:
            msg = await ctx.channel.fetch_message(message_id)
            await msg.delete()
        except:
            pass
    
    # Remove war data
    del wars[ctx.channel.id]
    save_data()
    
    # Delete all bot messages in channel
    async for msg in ctx.channel.history(limit=50):
        if msg.author == bot.user:
            try:
                await msg.delete()
            except:
                pass
    
    await ctx.send(f"✅ **WAR ENDED!** Status table cleared.")
    await asyncio.sleep(3)
    await ctx.message.delete()

@bot.command(name='warstatus')
async def war_status(ctx):
    """Show current war status table
    Usage: !warstatus"""
    
    if ctx.channel.id not in wars:
        await ctx.send(f"❌ No active war in this channel!")
    else:
        table = generate_war_table(ctx.channel.id)
        if table:
            await ctx.send(table)
        else:
            await ctx.send(f"⚠️ Error generating war table")
    
    await asyncio.sleep(10)
    await ctx.message.delete()

# ============= PREFIX COMMAND =============

@bot.command(name='prefixset')
@commands.has_permissions(administrator=True)
async def prefix_set(ctx, new_prefix: str):
    """Change bot prefix for this server
    Usage: !prefixset ?"""
    
    if len(new_prefix) > 5:
        await ctx.send("❌ Prefix too long! Max 5 characters.")
        await ctx.message.delete()
        return
    
    prefixes[ctx.guild.id] = new_prefix
    save_data()
    
    await ctx.send(f"✅ Prefix changed to `{new_prefix}`")
    await asyncio.sleep(3)
    await ctx.message.delete()

# ============= CREATE GANG =============

@bot.command(name='rostercreate')
@commands.has_permissions(administrator=True)
async def roster_create(ctx, gang: str):
    """Create a new gang
    Usage: !rostercreate gangname"""
    
    gang = gang.lower()
    
    if gang in rosters:
        await ctx.send(f"❌ Gang **{gang}** already exists!")
    else:
        rosters[gang] = []
        save_data()
        await ctx.send(f"✅ Gang **{gang}** created!")
    
    await asyncio.sleep(3)
    await ctx.message.delete()

# ============= ADD MEMBERS =============

@bot.command(name='rosteradd')
@commands.has_permissions(administrator=True)
async def roster_add(ctx, gang: str, *, members: str):
    """Add members to a gang
    Usage: !rosteradd gangname ign @mention, ign2 @mention2 @mention3, ign3 @mention3"""
    
    gang = gang.lower()
    
    if gang not in rosters:
        await ctx.send(f"❌ Gang **{gang}** doesn't exist! Use `!rostercreate {gang}` first.")
        await ctx.message.delete()
        return
    
    # Parse members
    new_members = parse_members(members)
    
    if not new_members:
        await ctx.send(f"❌ Invalid format. Use: `!rosteradd {gang} ign @mention, ign2 @mention`")
        await ctx.message.delete()
        return
    
    # Add members
    added = []
    for member in new_members:
        ign = member['ign']
        discord_ids = member['discord_ids']
        
        # Check if IGN already exists
        exists = False
        for existing in rosters[gang]:
            if existing['ign'].lower() == ign.lower():
                exists = True
                # Merge discord IDs
                for did in discord_ids:
                    if did not in existing['discord_ids']:
                        existing['discord_ids'].append(did)
                added.append(f"{ign} (added {len(discord_ids)} Discord)")
                break
        
        if not exists:
            rosters[gang].append({'ign': ign, 'discord_ids': discord_ids})
            added.append(ign)
    
    save_data()
    
    # Show updated roster
    await ctx.send(format_roster(gang))
    await asyncio.sleep(5)
    await ctx.message.delete()

# ============= REMOVE MEMBERS =============

@bot.command(name='rosterremove')
@commands.has_permissions(administrator=True)
async def roster_remove(ctx, gang: str, *, identifier: str):
    """Remove a member from a gang by IGN or @mention
    Usage: !rosterremove gangname ign
           !rosterremove gangname @mention"""
    
    gang = gang.lower()
    
    if gang not in rosters:
        await ctx.send(f"❌ Gang **{gang}** doesn't exist!")
        await ctx.message.delete()
        return
    
    # Check if it's a mention
    mention_match = re.search(r'<@!?(\d+)>', identifier)
    if mention_match:
        discord_id = int(mention_match.group(1))
        # Find and remove member by discord_id
        to_remove = None
        for member in rosters[gang]:
            if discord_id in member.get('discord_ids', []):
                to_remove = member
                break
        
        if to_remove:
            rosters[gang].remove(to_remove)
            save_data()
            await ctx.send(f"✅ Removed **{to_remove['ign']}** from **{gang}**")
        else:
            await ctx.send(f"❌ No member found with that mention in **{gang}**")
    else:
        # Remove by IGN
        ign = identifier.strip()
        to_remove = None
        for member in rosters[gang]:
            if member['ign'].lower() == ign.lower():
                to_remove = member
                break
        
        if to_remove:
            rosters[gang].remove(to_remove)
            save_data()
            await ctx.send(f"✅ Removed **{to_remove['ign']}** from **{gang}**")
        else:
            await ctx.send(f"❌ No IGN named **{ign}** found in **{gang}**")
    
    # Show updated roster
    await asyncio.sleep(2)
    await ctx.send(format_roster(gang))
    await asyncio.sleep(5)
    await ctx.message.delete()

# ============= DELETE GANG =============

@bot.command(name='rosterdelete')
@commands.has_permissions(administrator=True)
async def roster_delete(ctx, gang: str):
    """Delete an entire gang
    Usage: !rosterdelete gangname"""
    
    gang = gang.lower()
    
    if gang not in rosters:
        await ctx.send(f"❌ Gang **{gang}** doesn't exist!")
    else:
        del rosters[gang]
        save_data()
        await ctx.send(f"✅ Gang **{gang}** has been deleted!")
    
    await asyncio.sleep(3)
    await ctx.message.delete()

# ============= SHOW ROSTER =============

@bot.command(name='rostershow')
async def roster_show(ctx, gang: str = None):
    """Show a specific gang or all gangs
    Usage: !rostershow gangname
           !rostershow all"""
    
    if not gang:
        await ctx.send(f"❌ Please specify a gang name or 'all'")
        await ctx.message.delete()
        return
    
    gang = gang.lower()
    
    if gang == 'all':
        if not rosters:
            await ctx.send("No gangs exist. Use `!rostercreate` to create one.")
        else:
            output = "**ALL GANGS**\n" + "=" * 40 + "\n\n"
            for g in rosters:
                output += format_roster(g) + "\n"
            
            if len(output) > 1900:
                for g in rosters:
                    await ctx.send(format_roster(g))
            else:
                await ctx.send(output)
    else:
        if gang not in rosters:
            await ctx.send(f"❌ Gang **{gang}** doesn't exist!")
        else:
            await ctx.send(format_roster(gang))
    
    await asyncio.sleep(10)
    try:
        await ctx.message.delete()
    except:
        pass

# ============= HELP =============

@bot.command(name='rosterhelp')
async def roster_help(ctx):
    """Show all commands"""
    prefix = prefixes.get(ctx.guild.id, DEFAULT_PREFIX)
    help_text = f"""
**🎮 GANG ROSTER & WAR BOT - COMMANDS**

**Roster Commands (Admin):**
- `{prefix}rostercreate gangname` - Create a new gang
- `{prefix}rosteradd gangname ign @mention, ign2 @mention2` - Add members
- `{prefix}rosterremove gangname ign/@mention` - Remove member
- `{prefix}rosterdelete gangname` - Delete an entire gang
- `{prefix}rostershow gangname/all` - Show gang(s)
- `{prefix}prefixset newprefix` - Change bot prefix

**War Commands (Admin):**
- `{prefix}warstart gangname` - Start a war status table in this channel
- `{prefix}warend` - End war and clear table in this channel

**War Commands (Everyone):**
- `{prefix}warstatus` - Show current war table
- `00f 123` or `0 0 f 1 2 3` - Post your status during war

**Status Format:**
- First number: Cars available
- Second number: Cars healing  
- Third number: Heals remaining (or F for full)
- Next 3 numbers: Building for Car 1, 2, 3 (1-6)

**Examples:**
- `{prefix}rostercreate royalty`
- `{prefix}rosteradd royalty Darkphoenix @colt @hyper, Colt @colt`
- `{prefix}warstart royalty`
- `00f 123`
- `011 456`
- `0 0 f 1 2 3`
- `{prefix}warstatus`
- `{prefix}warend`

**Features:**
- Multiple gangs with Discord-linked IGNs
- Multiple active wars in different channels simultaneously
- Auto-updating status tables
- Sleep mode (add 'zzz' to status)
"""
    await ctx.send(help_text)
    await asyncio.sleep(20)
    try:
        await ctx.message.delete()
    except:
        pass

# Run the bot
if __name__ == "__main__":
    TOKEN = os.environ.get('DISCORD_TOKEN')
    
    if TOKEN == 'YOUR_BOT_TOKEN_HERE':
        print("❌ Please replace 'YOUR_BOT_TOKEN_HERE' with your actual bot token!")
        print("Get your token from: https://discord.com/developers/applications")
    else:
        bot.run(TOKEN)