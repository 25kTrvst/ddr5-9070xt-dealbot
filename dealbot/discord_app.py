from __future__ import annotations

import asyncio
import io

import discord
from discord import app_commands
from discord.ext import commands

from .charts import render_price_history
from .config import Config
from .models import Deal, Kind
from .orchestrator import CRASH_RESTART_DELAY_SECONDS, Engine


class DealBot(commands.Bot):
    def __init__(self, cfg: Config):
        intents = discord.Intents.default()
        super().__init__(command_prefix="!", intents=intents)
        self.cfg = cfg; self.engine = Engine(cfg, self.post_deal, self.post_crash); self._engine_started = False

    async def setup_hook(self) -> None:
        await self.add_cog(DealCog(self))
        await self.tree.sync()

    async def on_ready(self) -> None:
        if not self._engine_started:
            self._engine_started = True; await self.engine.start()
        print(f"DealBot V6 online as {self.user}; independent scanners running")

    def _channel(self, kind: Kind):
        target = self.cfg.ram_channel_name if kind == "ram" else self.cfg.gpu_channel_name
        return discord.utils.find(lambda c: getattr(c, "name", "").lower() == target, self.get_all_channels())

    async def post_deal(self, deal: Deal) -> None:
        c, cl = deal.candidate, deal.classification
        channel = self._channel(deal.kind)
        if not channel: return
        if deal.unconfirmed:
            color = discord.Color.red()
        elif deal.recommendation.startswith("BUY"):
            color = discord.Color.green()
        elif deal.restocked:
            color = discord.Color.blue()
        else:
            color = discord.Color.gold()
        label = cl.identity_label if deal.kind == "gpu" else f"{cl.capacity_gb}GB DDR5 {cl.speed_mts} MT/s"
        icon = "⚠️" if deal.unconfirmed else ("🔄" if deal.restocked else ("✅" if deal.score >= 78 else "👀"))
        embed = discord.Embed(title=f"{icon} {label} — {deal.recommendation}", description=c.title[:4000], url=c.url, color=color)
        embed.add_field(name="Price", value=f"${c.price:.2f}", inline=True)
        embed.add_field(name="Estimated checkout", value=f"${deal.estimated_total:.2f}", inline=True)
        embed.add_field(name="Deal score", value=f"{deal.score}/100", inline=True)
        embed.add_field(name="Store", value=c.source, inline=True)
        embed.add_field(name="Condition / stock", value=f"{c.condition} / {c.stock}", inline=True)
        embed.add_field(name="Identity", value=f"{cl.confidence}/100\n`{cl.model_key}`", inline=True)
        if deal.market_sample_count >= 3 and deal.market_baseline is not None:
            embed.add_field(name=f"Market baseline ({deal.market_sample_count} sources)", value=f"${deal.market_baseline:.2f}", inline=True)
        if deal.low_30d_all_sources is not None:
            embed.add_field(name="30-day low (all stores)", value=f"${deal.low_30d_all_sources:.2f}", inline=True)
        if c.seller_feedback_score is not None:
            embed.add_field(name="eBay seller quality", value=f"{c.seller_feedback_score:,} feedback • {c.seller_feedback_percent:.1f}% positive", inline=False)
        if deal.unconfirmed:
            embed.add_field(name="⚠️ Unconfirmed price", value="Far below the normal range and seen on only one price surface so far. Double-check the listing yourself before buying.", inline=False)
        if deal.restocked:
            embed.add_field(name="🔄 Back in stock", value="This exact listing was out of stock and just became available again.", inline=False)
        embed.add_field(name="Why", value=deal.recommendation_reason[:1024], inline=False)
        embed.add_field(name="Verification", value=" • ".join(cl.reasons)[:1024], inline=False)
        embed.set_footer(text="DealBot V6 • exact identity gates • verified price • persistent SKU watchlist")
        view = discord.ui.View(timeout=None); view.add_item(discord.ui.Button(label="Open verified deal", url=c.url, emoji="🔗"))
        mention = f"<@{self.cfg.ping_user_id}>" if self.cfg.ping_user_id else None
        chart_file = None
        if self.cfg.price_chart_enabled:
            history = await self.engine.storage.price_history(deal.kind, cl.model_key, self.cfg.price_chart_history_days)
            png = render_price_history(history, cl.model_key or label)
            if png:
                chart_file = discord.File(io.BytesIO(png), filename="price_history.png")
                embed.set_image(url="attachment://price_history.png")
        await channel.send(content=mention, embed=embed, view=view, file=chart_file)

    async def post_crash(self, task_name: str, exc: Exception) -> None:
        target = discord.utils.find(lambda c: getattr(c, "name", "").lower() == self.cfg.ops_channel_name, self.get_all_channels())
        target = target or self._channel("gpu") or self._channel("ram")
        text = f"**{task_name}** crashed with `{type(exc).__name__}: {exc}`.\nIt has been restarted automatically — check `/status` for its current state."
        mention = f"<@{self.cfg.ping_user_id}>" if self.cfg.ping_user_id else None
        embed = discord.Embed(title="🚨 Scanner crashed", description=text[:4000], color=discord.Color.red())
        if target:
            await target.send(content=mention, embed=embed)
        elif self.cfg.ping_user_id:
            user = self.get_user(self.cfg.ping_user_id) or await self.fetch_user(self.cfg.ping_user_id)
            if user:
                await user.send(embed=embed)

    async def status_cmd(self, interaction: discord.Interaction):
        rows = await self.engine.storage.health()
        health = "\n".join(f"**{r['source']}** — {r['state']} • {r['detail']}" for r in rows) or "Waiting for the first scans."
        api = f"eBay: {'ready' if self.engine.ebay.configured else 'credentials missing'}\nBest Buy: {'ready' if self.engine.bestbuy.configured else 'key missing'}\nReddit: {'ready' if self.engine.discovery[0].configured else 'credentials/approval missing'}\nSlickdeals: {'ready' if self.engine.discovery[1].configured else 'feed URL not configured'}\nZoho: {'ready' if self.engine.discovery[2].configured else 'disabled'}"
        embed = discord.Embed(title="DealBot V6 status", color=discord.Color.blurple())
        embed.add_field(name="Fast lanes", value=f"eBay {self.cfg.ebay_interval_seconds}s • Best Buy {self.cfg.bestbuy_interval_seconds}s • Reddit {self.cfg.reddit_interval_seconds}s", inline=False)
        embed.add_field(name="Watch/discovery", value=f"Known SKUs {self.cfg.watchlist_interval_seconds}s • store searches {self.cfg.slow_interval_seconds}s • blocks {self.cfg.blocked_backoff_min_seconds//60}–{self.cfg.blocked_backoff_max_seconds//60}m", inline=False)
        embed.add_field(name="RAM speed tiers searched", value=", ".join(f"{s} MT/s" for s in self.cfg.ram_speeds), inline=False)
        embed.add_field(name="Crash alerts", value=f"Posted to #{self.cfg.ops_channel_name} (falls back to #{self.cfg.gpu_channel_name} or a DM) — a crashed scanner auto-restarts after {CRASH_RESTART_DELAY_SECONDS}s", inline=False)
        embed.add_field(name="Connections", value=api, inline=False)
        embed.add_field(name="Latest results", value=health[:1024], inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    async def _manual(self, interaction: discord.Interaction, kind: Kind):
        await interaction.response.defer(ephemeral=True, thinking=True)
        sources = [self.engine.ebay, self.engine.bestbuy, *self.engine.retailers]
        batches = await asyncio.gather(*(self.engine.scan_source(s, kind) for s in sources), return_exceptions=True)
        found = sum(len(x) for x in batches if isinstance(x, list))
        await interaction.followup.send(f"Finished the {kind.upper()} scan: {found} new alert(s). Automatic scanning was already running.", ephemeral=True)

    async def scanram_cmd(self, interaction: discord.Interaction): await self._manual(interaction, "ram")

    async def scangpu_cmd(self, interaction: discord.Interaction): await self._manual(interaction, "gpu")

    async def ignore_cmd(self, interaction: discord.Interaction, url: str):
        await self.engine.storage.ignore(url); await interaction.response.send_message("That exact URL is now ignored.", ephemeral=True)

    async def watch_cmd(self, interaction: discord.Interaction):
        await interaction.response.send_message("Every verified product is saved automatically by URL, source ID, SKU/UPC when available, and exact model key. It is rechecked every 2 minutes by default. You do not need to spam scan commands.", ephemeral=True)


class DealCog(commands.Cog):
    def __init__(self, bot: DealBot): self.bot = bot

    @app_commands.command(name="status", description="Show every scanner, schedule, and backoff state")
    async def status(self, interaction: discord.Interaction): await self.bot.status_cmd(interaction)

    @app_commands.command(name="scanram", description="Run one RAM scan now; automatic scanning continues")
    async def scanram(self, interaction: discord.Interaction): await self.bot.scanram_cmd(interaction)

    @app_commands.command(name="scangpu", description="Run one GPU scan now; automatic scanning continues")
    async def scangpu(self, interaction: discord.Interaction): await self.bot.scangpu_cmd(interaction)

    @app_commands.command(name="ignore", description="Never alert this exact listing URL again")
    async def ignore(self, interaction: discord.Interaction, url: str): await self.bot.ignore_cmd(interaction, url)

    @app_commands.command(name="watch", description="Explain the automatic SKU watchlist")
    async def watch(self, interaction: discord.Interaction): await self.bot.watch_cmd(interaction)


def run(cfg: Config) -> None:
    DealBot(cfg).run(cfg.discord_token, log_handler=None)
