"""
Simple stats tracker that reads/writes to a JSON file.
Easily update and query ball statistics.
"""

import json
from pathlib import Path
from typing import Dict, Any, Optional


class StatsManager:
    """Manage persistent battle statistics in JSON."""
    
    def __init__(self, stats_file: str = None):
        """
        Initialize stats manager.
        
        Args:
            stats_file: Path to stats.json (defaults to config/stats.json)
        """
        if stats_file is None:
            # Auto-find config/stats.json relative to this file
            base_dir = Path(__file__).parent.parent
            stats_file = base_dir / "config" / "stats.json"
        
        self.stats_file = Path(stats_file)
        self.data = self._load()
    
    def _load(self) -> dict:
        """Load stats from JSON file."""
        if self.stats_file.exists():
            with open(self.stats_file, 'r') as f:
                return json.load(f)
        return {"balls": []}
    
    def _save(self) -> None:
        """Save stats to JSON file."""
        with open(self.stats_file, 'w') as f:
            json.dump(self.data, f, indent=2)
    
    def get_ball(self, ball_id: int) -> Optional[Dict[str, Any]]:
        """Get stats for a specific ball by ID."""
        for ball in self.data.get("balls", []):
            if ball["id"] == ball_id:
                return ball
        return None
    
    def get_ball_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        """Get stats for a specific ball by name."""
        for ball in self.data.get("balls", []):
            if ball["name"].lower() == name.lower():
                return ball
        return None
    
    def add_win(self, ball_id: int) -> None:
        """Record a win for a ball."""
        ball = self.get_ball(ball_id)
        if ball:
            ball["wins"] += 1
            ball["total_battles"] += 1
            self._save()
    
    def add_loss(self, ball_id: int) -> None:
        """Record a loss for a ball."""
        ball = self.get_ball(ball_id)
        if ball:
            ball["losses"] += 1
            ball["total_battles"] += 1
            self._save()
    
    def add_kill(self, ball_id: int, count: int = 1) -> None:
        """Add kills to a ball's record."""
        ball = self.get_ball(ball_id)
        if ball:
            ball["kills"] += count
            self._save()
    
    def add_elimination(self, ball_id: int, count: int = 1) -> None:
        """Add eliminations to a ball's record."""
        ball = self.get_ball(ball_id)
        if ball:
            ball["eliminations"] += count
            self._save()
    
    def add_lifeline_cut(self, ball_id: int, count: int = 1) -> None:
        """Add lifeline cuts to a ball's record."""
        ball = self.get_ball(ball_id)
        if ball:
            ball["lifeline_cuts"] += count
            self._save()
    
    def add_collision(self, ball_id: int, count: int = 1) -> None:
        """Add collisions to a ball's record."""
        ball = self.get_ball(ball_id)
        if ball:
            ball["collisions"] += count
            self._save()
    
    def update_ball(self, ball_id: int, **kwargs) -> None:
        """Update multiple stats for a ball at once."""
        ball = self.get_ball(ball_id)
        if ball:
            for key, value in kwargs.items():
                if key in ball:
                    ball[key] += value
            self._save()
    
    def get_leaderboard(self, sort_by: str = "wins") -> list:
        """
        Get leaderboard sorted by a specific stat.
        
        Args:
            sort_by: Stat to sort by (wins, kills, eliminations, etc.)
        
        Returns:
            List of ball stats sorted by the specified stat (descending)
        """
        return sorted(
            self.data.get("balls", []),
            key=lambda b: b.get(sort_by, 0),
            reverse=True
        )
    
    def print_stats(self, ball_id: int) -> None:
        """Print formatted stats for a ball."""
        ball = self.get_ball(ball_id)
        if ball:
            print(f"\n{ball['name'].upper()} (Ball {ball['id']})")
            print("-" * 40)
            print(f"  Wins:              {ball['wins']}")
            print(f"  Losses:            {ball['losses']}")
            print(f"  Total Battles:     {ball['total_battles']}")
            print(f"  Kills:             {ball['kills']}")
            print(f"  Eliminations:      {ball['eliminations']}")
            print(f"  Lifeline Cuts:     {ball['lifeline_cuts']}")
            print(f"  Collisions:        {ball['collisions']}")
            if ball['total_battles'] > 0:
                win_rate = (ball['wins'] / ball['total_battles']) * 100
                print(f"  Win Rate:          {win_rate:.1f}%")
    
    def print_leaderboard(self, sort_by: str = "wins") -> None:
        """Print formatted leaderboard."""
        leaderboard = self.get_leaderboard(sort_by)
        print(f"\n{'LEADERBOARD (by ' + sort_by + ')':^50}")
        print("=" * 50)
        for i, ball in enumerate(leaderboard, 1):
            stat_value = ball.get(sort_by, 0)
            print(f"{i}. {ball['name']:10s} - {sort_by}: {stat_value}")
        print("=" * 50)


# Example usage
if __name__ == "__main__":
    # Initialize
    stats = StatsManager()
    
    # Simulate some battle results
    print("Simulating battles...")
    stats.add_win(0)  # Red wins
    stats.add_loss(1)  # Blue loses
    stats.add_kill(0, 2)  # Red got 2 kills
    stats.add_elimination(0, 2)  # Red eliminated 2 balls
    stats.add_lifeline_cut(0, 3)  # Red cut 3 lifelines
    
    stats.add_win(2)  # Green wins
    stats.add_loss(3)  # Yellow loses
    stats.add_kill(2, 1)  # Green got 1 kill
    
    # Display results
    stats.print_stats(0)
    stats.print_stats(2)
    stats.print_leaderboard("wins")
    stats.print_leaderboard("kills")
