import math
import re
import pandas as pd

TOURNEY_WEIGHTS = {
    "G": 1.5,  # Grand Slam
    "F": 1.4,  # Finals
    "M": 1.3,  # Masters
    "A": 1.2,  # ATP 500
    "B": 1.1,  # ATP 250
    "D": 1.0,  # Copa Davis
    "C": 0.9,  # Challenger
}

TOURNEY_NAMES = {
    "G": "Grand Slam",
    "F": "Finals",
    "M": "Masters 1000",
    "A": "ATP 500",
    "B": "ATP 250",
    "D": "Copa Davis",
    "C": "Challenger"
}

class MMRCalculator:
    def __init__(self, k=32, default_rating=1500):
        self.k = k
        self.default_rating = default_rating
        self.ratings = {}  # nome -> rating (float)
        self.surfaces = {}  # nome -> {"clay": r, "grass": r, ...}
        self.levels = {}  # nome -> {"G": r, "M": r, ...}
        self.combined = {}  # nome -> {"clay_M": r, "hard_G": r, ...}
        self.matches_played = {}  # nome -> número de partidas jogadas
        self.matches_by_surface = {}  # nome -> {"clay": n, "hard": n, ...}
        self.matches_by_level = {}  # nome -> {"G": n, "M": n, ...}
        self.matches_combined = {}  # nome -> {"clay_M": n, "hard_G": n, ...}

    def get_rating(self, player, surface=None, level=None):
        """Retorna o rating de um jogador, geral ou específico para superfície/torneio"""
        # Se ambos estão especificados, use o rating combinado
        if surface and level:
            combined_key = f"{surface}_{level}"
            if player in self.combined and combined_key in self.combined[player]:
                return self.combined[player][combined_key]
            return self.default_rating
            
        if surface:
            return self.surfaces.get(player, {}).get(surface, self.default_rating)
        if level:
            return self.levels.get(player, {}).get(level, self.default_rating)
        return self.ratings.get(player, self.default_rating)
    
    def ensure_player_initialized(self, name, surface, level):
        """Inicializa dados do jogador se necessário"""
        # Ratings gerais
        if name not in self.ratings:
            self.ratings[name] = self.default_rating
            self.matches_played[name] = 0
        
        # Ratings por superfície
        if name not in self.surfaces:
            self.surfaces[name] = {}
            self.matches_by_surface[name] = {}
        if surface and surface not in self.surfaces[name]:
            self.surfaces[name][surface] = self.default_rating
            self.matches_by_surface[name][surface] = 0
            
        # Ratings por nível de torneio
        if name not in self.levels:
            self.levels[name] = {}
            self.matches_by_level[name] = {}
        if level and level not in self.levels[name]:
            self.levels[name][level] = self.default_rating
            self.matches_by_level[name][level] = 0
            
        # Ratings combinados (superfície + nível)
        if name not in self.combined:
            self.combined[name] = {}
            self.matches_combined[name] = {}
        
        if surface and level:
            combined_key = f"{surface}_{level}"
            if combined_key not in self.combined[name]:
                self.combined[name][combined_key] = self.default_rating
                self.matches_combined[name][combined_key] = 0

    def parse_score(self, score):
        if pd.isna(score) or not isinstance(score, str):
            return 1.0

        # Remove parênteses e textos como 'RET', 'W/O', etc.
        clean_score = re.sub(r'\(.*?\)|[A-Za-z/]+', '', score).strip()
        
        sets_won = {"winner": 0, "loser": 0}
        total_games_diff = 0

        for set_score in clean_score.split():
            if '-' not in set_score:
                continue
            try:
                w, l = map(int, set_score.split('-'))
                sets_won["winner"] += w > l
                sets_won["loser"] += l > w
                total_games_diff += abs(w - l)
            except ValueError:
                continue

        set_diff = sets_won["winner"] - sets_won["loser"]
        if set_diff <= 0:
            return 1.0

        return min(2.0, 1.0 + 0.1 * set_diff + 0.01 * total_games_diff)

    def calculate_seed_factor(self, win_seed, loser_seed):
        """Calcula fator baseado nas seeds dos jogadores"""
        # Inicializa com valor neutro
        seed_factor = 1.0
        
        # Se ambas as seeds existem, podemos comparar
        if win_seed is not None and loser_seed is not None:
            # Se o perdedor tinha seed melhor (menor número)
            if loser_seed < win_seed:
                # Quanto maior a diferença, maior o fator
                seed_factor = 1.0 + min(0.5, (win_seed - loser_seed) / 10)
            # Se o vencedor tinha seed muito melhor que o perdedor
            elif win_seed < loser_seed and (loser_seed - win_seed) > 8:
                # Vitória esperada = menos pontos
                seed_factor = max(0.7, 1.0 - (loser_seed - win_seed) / 20)
                
        return seed_factor

    def update_rating(self, winner, loser, score, surface, tourney_level, win_seed=None, loser_seed=None):
        """Atualiza os ratings baseado no resultado da partida"""
        # Garante que os jogadores existam no sistema
        self.ensure_player_initialized(winner, surface, tourney_level)
        self.ensure_player_initialized(loser, surface, tourney_level)

        # Obtém ratings atuais
        rw = self.get_rating(winner)
        rl = self.get_rating(loser)
        
        # Ratings específicos por superfície
        rw_surface = self.get_rating(winner, surface=surface)
        rl_surface = self.get_rating(loser, surface=surface)
        
        # Ratings específicos por nível de torneio
        rw_level = self.get_rating(winner, level=tourney_level)
        rl_level = self.get_rating(loser, level=tourney_level)
        
        # Ratings combinados (superfície + nível)
        rw_combined = self.get_rating(winner, surface=surface, level=tourney_level)
        rl_combined = self.get_rating(loser, surface=surface, level=tourney_level)
        
        # Converte seeds para formato numérico se possível
        try:
            win_seed = int(win_seed) if win_seed is not None and pd.notna(win_seed) else None
        except (ValueError, TypeError):
            win_seed = None
            
        try:
            loser_seed = int(loser_seed) if loser_seed is not None and pd.notna(loser_seed) else None
        except (ValueError, TypeError):
            loser_seed = None

        # Calcula fatores de ajuste
        seed_factor = self.calculate_seed_factor(win_seed, loser_seed)
        score_factor = self.parse_score(score)
        level_weight = TOURNEY_WEIGHTS.get(str(tourney_level).upper(), 1.0)  # Convertido para string
        
        # Probabilidade esperada de vitória (ELO padrão)
        expected_w = 1 / (1 + 10 ** ((rl - rw) / 400))
        
        # Probabilidade esperada considerando superfície + nível (50% geral, 25% superfície, 25% nível)
        expected_w_combined = 1 / (1 + 10 ** (((rl + rl_surface + rl_level + rl_combined) - 
                                               (rw + rw_surface + rw_level + rw_combined)) / 1600))
        
        # Média das duas expectativas
        expected_w_final = (expected_w + expected_w_combined) / 2
        
        # Fator de experiência (K menor para jogadores com mais partidas)
        k_winner = self.k / (1 + self.matches_played.get(winner, 0) / 100)
        k_loser = self.k / (1 + self.matches_played.get(loser, 0) / 100)
        
        # Calcula delta base
        delta_base = score_factor * seed_factor * level_weight * (1 - expected_w_final)
        
        # Delta ajustado para cada jogador
        delta_winner = k_winner * delta_base
        delta_loser = k_loser * delta_base
        
        # Atualiza contadores de partidas
        self.matches_played[winner] = self.matches_played.get(winner, 0) + 1
        self.matches_played[loser] = self.matches_played.get(loser, 0) + 1
        
        # Atualiza contadores de partidas por superfície
        if surface:
            self.matches_by_surface[winner][surface] = self.matches_by_surface[winner].get(surface, 0) + 1
            self.matches_by_surface[loser][surface] = self.matches_by_surface[loser].get(surface, 0) + 1
        
        # Atualiza contadores de partidas por nível
        if tourney_level:
            self.matches_by_level[winner][tourney_level] = self.matches_by_level[winner].get(tourney_level, 0) + 1
            self.matches_by_level[loser][tourney_level] = self.matches_by_level[loser].get(tourney_level, 0) + 1
        
        # Atualiza contadores de partidas combinadas
        if surface and tourney_level:
            combined_key = f"{surface}_{tourney_level}"
            self.matches_combined[winner][combined_key] = self.matches_combined[winner].get(combined_key, 0) + 1
            self.matches_combined[loser][combined_key] = self.matches_combined[loser].get(combined_key, 0) + 1
        
        # Atualiza ratings gerais
        self.ratings[winner] += delta_winner
        self.ratings[loser] -= delta_loser

        # Atualiza ratings por superfície
        if surface:
            self.surfaces[winner][surface] += delta_winner
            self.surfaces[loser][surface] -= delta_loser

        # Atualiza ratings por tipo de torneio
        if tourney_level:
            self.levels[winner][tourney_level] += delta_winner
            self.levels[loser][tourney_level] -= delta_loser
            
        # Atualiza ratings combinados
        if surface and tourney_level:
            combined_key = f"{surface}_{tourney_level}"
            self.combined[winner][combined_key] += delta_winner
            self.combined[loser][combined_key] -= delta_loser
        
        return {
            "delta_winner": delta_winner,
            "delta_loser": delta_loser,
            "factors": {
                "seed": seed_factor,
                "score": score_factor,
                "tourney": level_weight,
                "expected": expected_w_final
            }
        }
    
    def get_combined_rankings(self, surface=None, level=None, min_matches=3):
        """Retorna ranking combinado por superfície e tipo de torneio"""
        result = {}
        
        # Se ambos estiverem definidos, retorna o ranking específico
        if surface and level:
            combined_key = f"{surface}_{level}"
            for player in self.combined:
                if combined_key in self.combined[player] and self.matches_combined[player].get(combined_key, 0) >= min_matches:
                    result[player] = self.combined[player][combined_key]
        
        # Se apenas a superfície estiver definida
        elif surface:
            for player in self.surfaces:
                if surface in self.surfaces[player] and self.matches_by_surface[player].get(surface, 0) >= min_matches:
                    result[player] = self.surfaces[player][surface]
        
        # Se apenas o nível estiver definido
        elif level:
            for player in self.levels:
                if level in self.levels[player] and self.matches_by_level[player].get(level, 0) >= min_matches:
                    result[player] = self.levels[player][level]
        
        # Sem filtros, retorna o ranking geral
        else:
            result = {player: rating for player, rating in self.ratings.items() 
                     if self.matches_played.get(player, 0) >= min_matches}
            
        return result