import pandas as pd
import os
from jinja2 import Template
import datetime

# Configuration
BASE_DIR = '/Users/ph/Desktop/Python/PremieRvet'
ORG_FILE = os.path.join(BASE_DIR, 'PRM_Mar_Org.xlsx')
PAID_FILE = os.path.join(BASE_DIR, 'PRM_Mar_Pago.xlsx')
OUTPUT_FILE = os.path.join(BASE_DIR, 'relatorio_posts_mar.html')
ICONS_DIR = 'icons'  # Relative to OUTPUT_FILE

def load_data():
    # Load Data
    org_df = pd.read_excel(ORG_FILE)
    paid_df = pd.read_excel(PAID_FILE)

    # Clean columns (strip whitespace just in case)
    org_df.columns = [c.strip() for c in org_df.columns]
    paid_df.columns = [c.strip() for c in paid_df.columns]

    # Ensure ID is string or int consistent for merging
    # Assuming ID is numeric, but let's make sure
    org_df['ID'] = pd.to_numeric(org_df['ID'], errors='coerce')
    paid_df['ID'] = pd.to_numeric(paid_df['ID'], errors='coerce')

    # Merge
    merged = pd.merge(org_df, paid_df, on='ID', how='outer', suffixes=('_org', '_paid'))

    # Fill NaNs for numeric columns
    numeric_cols = ['Views_org', 'Alcance_org', 'Interações_org', 'Taxa de Interação_org',
                    'Views_paid', 'Alcance_paid', 'Interações_paid', 'Taxa de Interação_paid', 'Valor investido']
    
    for col in numeric_cols:
        if col in merged.columns:
            merged[col] = merged[col].fillna(0)
    
    # Calculate Totals
    merged['Total_Views'] = merged.get('Views_org', 0) + merged.get('Views_paid', 0)
    merged['Total_Alcance'] = merged.get('Alcance_org', 0) + merged.get('Alcance_paid', 0)
    merged['Total_Interacoes'] = merged.get('Interações_org', 0) + merged.get('Interações_paid', 0)
    # New Taxa Calculation: Total Interactions / Total Alcance
    # Avoid division by zero
    merged['Total_Taxa'] = merged.apply(
        lambda row: row['Total_Interacoes'] / row['Total_Alcance'] 
        if row['Total_Alcance'] > 0 else 0, axis=1
    )

    return merged

def format_value(val, type_):
    if type_ == 'int':
        return f"{int(val):,}".replace(',', '.')
    elif type_ == 'percent':
        return f"{val:.1%}".replace('.', ',')
    elif type_ == 'currency':
        return f"R$ {val:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
    return val

def get_formatted_date(date_val):
    if pd.isna(date_val):
        return ""
    if isinstance(date_val, str):
        # Try parsing DD/MM/YYYY
        try:
            parts = date_val.split('/')
            if len(parts) >= 2:
                return f"{parts[0]}/{parts[1]}"
            return date_val
        except:
            return ""
    if isinstance(date_val, datetime.datetime):
        return date_val.strftime("%d/%m")
    return ""

def generate_html(df):
    html_template = """
<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Relatório de Performance | PremieRvet</title>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;800&family=Inter:wght@300;400;500;600&display=swap');

        :root {
            --primary: #023460;
            --secondary: #ff6600;
            --bg-body: #f0f2f5;
            --card-bg: #ffffff;
            --text-main: #1e293b;
            --text-muted: #64748b;
            --accent-gradient: linear-gradient(135deg, #023460 0%, #1a4b8c 100%);
            --shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.1), 0 8px 10px -6px rgba(0, 0, 0, 0.1);
            --transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
        }

        * {
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }

        body {
            font-family: 'Inter', sans-serif;
            background-color: var(--bg-body);
            color: var(--text-main);
            padding: 40px 20px;
            -webkit-font-smoothing: antialiased;
        }

        header {
            max-width: 1400px;
            margin: 0 auto 50px;
            text-align: center;
        }

        header h1 {
            font-family: 'Outfit', sans-serif;
            font-weight: 800;
            font-size: 3.5rem;
            background: var(--accent-gradient);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            margin-bottom: 10px;
            letter-spacing: -1px;
        }

        header p {
            font-size: 1.1rem;
            color: var(--text-muted);
            font-weight: 400;
        }

        .container {
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 30px;
            max-width: 1800px;
            margin: 0 auto;
        }

        .card {
            background: var(--card-bg);
            border-radius: 24px;
            overflow: hidden;
            box-shadow: var(--shadow);
            transition: var(--transition);
            border: 1px solid rgba(255, 255, 255, 0.8);
            display: flex;
            flex-direction: column;
        }

        .card:hover {
            transform: translateY(-8px);
            box-shadow: 0 20px 30px -10px rgba(0, 0, 0, 0.15);
        }

        .image-container {
            position: relative;
            width: 100%;
            padding-top: 100%;
            background-color: #f1f5f9;
            overflow: hidden;
        }

        .post-image {
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            object-fit: cover;
            transition: var(--transition);
        }

        .card:hover .post-image {
            transform: scale(1.05);
        }

        .overlay {
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: linear-gradient(to right, rgba(2, 52, 96, 0.9) 0%, rgba(2, 52, 96, 0.4) 60%, transparent 100%);
            color: white;
            padding: 30px;
            display: flex;
            align-items: center;
            opacity: 1;
            transition: var(--transition);
        }

        .date-badge {
            background: var(--secondary);
            color: white;
            font-family: 'Outfit', sans-serif;
            font-weight: 700;
            font-size: 14px;
            padding: 6px 16px;
            border-radius: 20px;
            position: absolute;
            top: 20px;
            right: 20px;
            z-index: 10;
            box-shadow: 0 4px 10px rgba(255, 102, 0, 0.3);
        }

        .metrics-overlay {
            display: flex;
            flex-direction: column;
            gap: 20px;
        }

        .metric-item {
            display: flex;
            align-items: center;
            gap: 15px;
            font-size: 1.1rem;
            font-weight: 500;
            font-family: 'Outfit', sans-serif;
        }

        .metric-item img {
            width: 28px;
            height: 28px;
            object-fit: contain;
            filter: drop-shadow(0 2px 4px rgba(0,0,0,0.2));
        }

        .comparison-table {
            width: 100%;
            border-collapse: separate;
            border-spacing: 0;
        }
        
        .comparison-table th {
            background-color: #f8fafc;
            color: var(--primary);
            padding: 15px;
            text-align: center;
            font-family: 'Outfit', sans-serif;
            font-weight: 700;
            font-size: 0.9rem;
            text-transform: uppercase;
            letter-spacing: 1px;
            border-bottom: 2px solid #e2e8f0;
        }
        
        .comparison-table td {
            padding: 12px 20px;
            font-size: 0.95rem;
            border-bottom: 1px solid #f1f5f9;
        }
        
        .label-cell {
            text-align: left;
            color: var(--text-muted);
            font-weight: 500;
        }
        
        .value-cell {
            text-align: right;
            font-weight: 600;
            color: var(--text-main);
        }

        .invest-row {
            background-color: #fffaf0;
        }

        .invest-row td {
            color: var(--secondary);
            font-weight: 700;
        }

        @media (max-width: 1400px) {
            .container {
                grid-template-columns: repeat(2, 1fr);
            }
        }

        @media (max-width: 768px) {
            .container {
                grid-template-columns: 1fr;
            }
            header h1 {
                font-size: 2.5rem;
            }
        }
    </style>
</head>
<body>
    <header>
        <h1>Relatório de Performance</h1>
        <p>Análise de Engajamento e Alcance - Março 2026</p>
    </header>

    <div class="container">
        {% for post in posts %}
        <div class="card">
            <div class="image-container">
                <img src="{{ post.image }}" alt="Post Image" class="post-image">
                <div class="date-badge">PUBLICADO EM {{ post.day }}</div>
                <div class="overlay">
                    <div class="metrics-overlay">
                        <div class="metric-item">
                            <img src="icons/views.png" alt="Views">
                            <span>{{ post.total_views }} <small style="font-size: 0.7em; opacity: 0.8; display: block; font-weight: 400;">Impressões Totais</small></span>
                        </div>
                        <div class="metric-item">
                            <img src="icons/alcance.png" alt="Alcance">
                            <span>{{ post.total_alcance }} <small style="font-size: 0.7em; opacity: 0.8; display: block; font-weight: 400;">Contas Alcançadas</small></span>
                        </div>
                        <div class="metric-item">
                            <img src="icons/interacoes.png" alt="Interações">
                            <span>{{ post.total_interacoes }} <small style="font-size: 0.7em; opacity: 0.8; display: block; font-weight: 400;">Engajamento Total</small></span>
                        </div>
                        <div class="metric-item">
                            <img src="icons/taxa_interaco.png" alt="Taxa">
                            <span>{{ post.total_taxa }} <small style="font-size: 0.7em; opacity: 0.8; display: block; font-weight: 400;">Taxa de Engajamento</small></span>
                        </div>
                    </div>
                </div>
            </div>
            
            <table class="comparison-table">
                <thead>
                    <tr>
                        <th colspan="2">Orgânico</th>
                        <th colspan="2">Pago</th>
                    </tr>
                </thead>
                <tbody>
                    <tr>
                        <td class="label-cell">Impressões</td>
                        <td class="value-cell">{{ post.org_views }}</td>
                        <td class="label-cell">Impressões</td>
                        <td class="value-cell">{{ post.paid_views }}</td>
                    </tr>
                    <tr>
                        <td class="label-cell">Alcance</td>
                        <td class="value-cell">{{ post.org_alcance }}</td>
                        <td class="label-cell">Alcance</td>
                        <td class="value-cell">{{ post.paid_alcance }}</td>
                    </tr>
                    <tr>
                        <td class="label-cell">Interações</td>
                        <td class="value-cell">{{ post.org_interacoes }}</td>
                        <td class="label-cell">Interações</td>
                        <td class="value-cell">{{ post.paid_interacoes }}</td>
                    </tr>
                    <tr>
                        <td class="label-cell">Engajamento</td>
                        <td class="value-cell">{{ post.org_taxa }}</td>
                        <td class="label-cell">Engajamento</td>
                        <td class="value-cell">{{ post.paid_taxa }}</td>
                    </tr>
                    <tr class="invest-row">
                        <td colspan="2" style="border:none;"></td>
                        <td class="label-cell" style="color: var(--secondary)">Investimento</td>
                        <td class="value-cell">{{ post.paid_investimento }}</td>
                    </tr>
                </tbody>
            </table>
        </div>
        {% endfor %}
    </div>
</body>
</html>
    """
    
    posts_data = []
    for _, row in df.iterrows():
        post = {
            'image': row.get('Imagem', ''),
            'day': get_formatted_date(row.get('Data', '')),
            
            'total_views': format_value(row['Total_Views'], 'int'),
            'total_alcance': format_value(row['Total_Alcance'], 'int'),
            'total_interacoes': format_value(row['Total_Interacoes'], 'int'),
            'total_taxa': format_value(row['Total_Taxa'], 'percent'),
            
            'org_views': format_value(row.get('Views_org', 0), 'int'),
            'org_alcance': format_value(row.get('Alcance_org', 0), 'int'),
            'org_interacoes': format_value(row.get('Interações_org', 0), 'int'),
            'org_taxa': format_value(row.get('Taxa de Interação_org', 0), 'percent'),
            
            'paid_views': format_value(row.get('Views_paid', 0), 'int'),
            'paid_alcance': format_value(row.get('Alcance_paid', 0), 'int'),
            'paid_interacoes': format_value(row.get('Interações_paid', 0), 'int'),
            'paid_taxa': format_value(row.get('Taxa de Interação_paid', 0), 'percent'),
            'paid_investimento': format_value(row.get('Valor investido', 0), 'currency'),
        }
        posts_data.append(post)
        
    template = Template(html_template)
    html_content = template.render(posts=posts_data)
    
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        f.write(html_content)
    
    print(f"Report generated at: {OUTPUT_FILE}")

if __name__ == "__main__":
    df = load_data()
    generate_html(df)
