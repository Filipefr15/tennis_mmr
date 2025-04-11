import pandas as pd
import glob
from mmr_calculator import MMRCalculator, TOURNEY_WEIGHTS, TOURNEY_NAMES

def load_data(pattern="data/atp_matches_*.csv"):
    """Carrega e combina os dados dos arquivos CSV"""
    csv_files = glob.glob(pattern)
    
    if not csv_files:
        raise FileNotFoundError(f"Nenhum arquivo encontrado com o padrão: {pattern}")
    
    df_list = [pd.read_csv(file) for file in csv_files]
    return pd.concat(df_list, ignore_index=True)

def process_matches(df, mmr):
    """Processa as partidas e atualiza os ratings"""
    # Filtro opcional para remover dados incompletos
    df = df.dropna(subset=['winner_name', 'loser_name'])
    
    # Contador para acompanhar o progresso
    total_matches = len(df)
    processed = 0
    
    results = []
    
    for _, row in df.iterrows():
        winner = row['winner_name']
        loser = row['loser_name']
        surface = str(row['surface']).lower() if pd.notna(row['surface']) else 'unknown'
        score = row['score'] if 'score' in row and pd.notna(row['score']) else None
        tourney_level = row['tourney_level'] if 'tourney_level' in row and pd.notna(row['tourney_level']) else 'X'
        win_seed = row['winner_seed'] if 'winner_seed' in row and pd.notna(row['winner_seed']) else None
        loser_seed = row['loser_seed'] if 'loser_seed' in row and pd.notna(row['loser_seed']) else None
        
        try:
            # Atualiza ratings
            update_result = mmr.update_rating(winner, loser, score, surface, tourney_level, win_seed, loser_seed)
            
            # Armazena resultados para análise
            results.append({
                'tourney_name': row['tourney_name'] if 'tourney_name' in row else 'Unknown',
                'tourney_date': row['tourney_date'] if 'tourney_date' in row else 'Unknown',
                'winner': winner,
                'loser': loser,
                'surface': surface,
                'level': tourney_level,
                'delta_winner': update_result['delta_winner'],
                'delta_loser': update_result['delta_loser'],
                'score': score
            })
        except Exception as e:
            print(f"Erro ao processar partida: {winner} vs {loser} - {e}")
        
        # Atualiza contador
        processed += 1
        if processed % 1000 == 0 or processed == total_matches:
            print(f"Processado: {processed}/{total_matches} partidas ({processed/total_matches*100:.1f}%)")
    
    return pd.DataFrame(results)

def print_rankings(mmr, category="geral", surface=None, level=None, top_n=10, min_matches=3):
    """Imprime os rankings conforme a categoria selecionada"""
    # Obtém os ratings para a categoria específica
    ratings = mmr.get_combined_rankings(surface, level, min_matches)
    
    if not ratings:
        print(f"Nenhum jogador encontrado com os critérios especificados (mínimo {min_matches} partidas)")
        return
    
    # Ordena por rating
    ranking = sorted(ratings.items(), key=lambda x: x[1], reverse=True)
    
    # Título composto
    title_parts = []
    if level:
        title_parts.append(TOURNEY_NAMES.get(level, level))
    if surface:
        title_parts.append(f"superfície {surface.capitalize()}")
    
    title = f"Top {top_n} MMR" + (f" - {' em '.join(title_parts)}" if title_parts else " (geral)")
    print(f"\n{title}:")
    
    # Imprime ranking
    for i, (name, rating) in enumerate(ranking[:top_n], 1):
        # Exibe número de partidas jogadas no contexto específico
        if surface and level:
            matches = mmr.matches_combined[name].get(f"{surface}_{level}", 0)
        elif surface:
            matches = mmr.matches_by_surface[name].get(surface, 0)
        elif level:
            matches = mmr.matches_by_level[name].get(level, 0)
        else:
            matches = mmr.matches_played.get(name, 0)
            
        print(f"{i}. {name}: {round(rating, 2)} ({matches} partidas)")
    
    return ranking[:top_n]

def analyze_player(mmr, player_name):
    """Analisa e exibe estatísticas de um jogador específico"""
    if player_name not in mmr.ratings:
        print(f"Jogador não encontrado: {player_name}")
        return
    
    print(f"\n--- Análise de {player_name} ---")
    print(f"Rating geral: {round(mmr.ratings[player_name], 2)}")
    print(f"Partidas jogadas: {mmr.matches_played.get(player_name, 0)}")
    
    # Ratings por superfície
    print("\nRatings por superfície:")
    if player_name in mmr.surfaces:
        for surface, rating in sorted(mmr.surfaces[player_name].items(), key=lambda x: x[1], reverse=True):
            matches = mmr.matches_by_surface[player_name].get(surface, 0)
            print(f"- {surface.capitalize()}: {round(rating, 2)} ({matches} partidas)")
    
    # Ratings por nível de torneio
    print("\nRatings por nível de torneio:")
    if player_name in mmr.levels:
        for level, rating in sorted(mmr.levels[player_name].items(), key=lambda x: x[1], reverse=True):
            matches = mmr.matches_by_level[player_name].get(level, 0)
            tourney_type = TOURNEY_NAMES.get(level, level)
            print(f"- {tourney_type}: {round(rating, 2)} ({matches} partidas)")
    
    # Top 3 combinações (superfície + nível)
    print("\nMelhores combinações (superfície + nível):")
    if player_name in mmr.combined:
        combined_ratings = [(k, v, mmr.matches_combined[player_name].get(k, 0)) 
                          for k, v in mmr.combined[player_name].items()]
        combined_ratings.sort(key=lambda x: x[1], reverse=True)
        
        for i, (key, rating, matches) in enumerate(combined_ratings[:5], 1):
            if matches < 2:  # Ignora combinações com poucas partidas
                continue
                
            surface, level = key.split('_')
            tourney_type = TOURNEY_NAMES.get(level, level)
            print(f"{i}. {surface.capitalize()} + {tourney_type}: {round(rating, 2)} ({matches} partidas)")

def main():
    # Carrega dados
    print("Carregando dados...")
    try:
        df = load_data()
        print(f"Dados carregados: {len(df)} partidas")
    except FileNotFoundError as e:
        print(f"Erro: {e}")
        return
    
    # Inicializa calculadora de MMR
    mmr = MMRCalculator(k=32)
    
    # Processa partidas
    print("Processando partidas...")
    results_df = process_matches(df, mmr)
    
    # Imprime rankings
    print_rankings(mmr, top_n=20)
    
    # Imprime rankings por superfície se houver dados suficientes
    surfaces = ["clay", "hard", "grass"]
    for surface in surfaces:
        if any(surface in player_surfaces for player_surfaces in mmr.surfaces.values()):
            print_rankings(mmr, surface=surface, top_n=10)
    
    # Menu interativo
    while True:
        print("\n--- Menu ---")
        print("1. Ver ranking geral")
        print("2. Ver ranking por superfície")
        print("3. Ver ranking por nível de torneio")
        print("4. Ver ranking combinado (superfície + nível)")
        print("5. Analisar jogador específico")
        print("6. Sair")
        
        choice = input("Escolha uma opção: ")
        
        if choice == "1":
            top_n = input("Quantos jogadores exibir? (padrão: 20) ")
            top_n = int(top_n) if top_n.isdigit() else 20
            min_matches = input("Mínimo de partidas? (padrão: 3) ")
            min_matches = int(min_matches) if min_matches.isdigit() else 3
            print_rankings(mmr, top_n=top_n, min_matches=min_matches)
            
        elif choice == "2":
            surface = input("Qual superfície? (clay/hard/grass) ").lower()
            if surface not in surfaces:
                print(f"Superfície inválida. Opções: {', '.join(surfaces)}")
                continue
            top_n = input("Quantos jogadores exibir? (padrão: 10) ")
            top_n = int(top_n) if top_n.isdigit() else 10
            min_matches = input("Mínimo de partidas? (padrão: 3) ")
            min_matches = int(min_matches) if min_matches.isdigit() else 3
            print_rankings(mmr, surface=surface, top_n=top_n, min_matches=min_matches)
            
        elif choice == "3":
            level = input("Qual nível? (G=Grand Slam, M=Masters, A=ATP500, B=ATP250) ").upper()
            if level not in TOURNEY_WEIGHTS.keys():
                print(f"Nível inválido. Opções: {', '.join(TOURNEY_WEIGHTS.keys())}")
                continue
            top_n = input("Quantos jogadores exibir? (padrão: 10) ")
            top_n = int(top_n) if top_n.isdigit() else 10
            min_matches = input("Mínimo de partidas? (padrão: 3) ")
            min_matches = int(min_matches) if min_matches.isdigit() else 3
            print_rankings(mmr, level=level, top_n=top_n, min_matches=min_matches)
            
        elif choice == "4":
            surface = input("Qual superfície? (clay/hard/grass) ").lower()
            if surface not in surfaces:
                print(f"Superfície inválida. Opções: {', '.join(surfaces)}")
                continue
                
            level = input("Qual nível? (G=Grand Slam, M=Masters, A=ATP500, B=ATP250) ").upper()
            if level not in TOURNEY_WEIGHTS.keys():
                print(f"Nível inválido. Opções: {', '.join(TOURNEY_WEIGHTS.keys())}")
                continue
                
            top_n = input("Quantos jogadores exibir? (padrão: 10) ")
            top_n = int(top_n) if top_n.isdigit() else 10
            
            min_matches = input("Mínimo de partidas? (padrão: 2) ")
            min_matches = int(min_matches) if min_matches.isdigit() else 2
            
            print_rankings(mmr, surface=surface, level=level, top_n=top_n, min_matches=min_matches)
            
        elif choice == "5":
            player = input("Nome do jogador: ")
            analyze_player(mmr, player)
            
        elif choice == "6":
            break
            
        else:
            print("Opção inválida!")

if __name__ == "__main__":
    main()