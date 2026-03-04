import pandas as pd
import os
from jinja2 import Template
import datetime

# Configuration
BASE_DIR = '/Users/ph/Desktop/Python/PremieRvet'
ORG_FILE = os.path.join(BASE_DIR, 'PRM_Nov_Org.xlsx')
PAID_FILE = os.path.join(BASE_DIR, 'PRM_Nov_Pago.xlsx')
OUTPUT_FILE = os.path.join(BASE_DIR, 'relatorio_posts.html')
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
    <title>Relatório de Posts</title>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Roboto:wght@400;500;700&display=swap');

        body {
            font-family: 'Roboto', sans-serif;
            background-color: #f5f5f5;
            margin: 0;
            padding: 20px;
            display: flex;
            justify-content: center;
        }

        .container {
            width: 100%;
            max-width: 1910px;
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(400px, 1fr));
            gap: 30px;
        }

        .card {
            background: white;
            border-radius: 10px;
            overflow: hidden;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            display: flex;
            flex-direction: column;
        }

        .image-container {
            position: relative;
            width: 100%;
            padding-top: 100%; /* 1:1 Aspect Ratio */
            background-color: #333;
        }

        .post-image {
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            object-fit: cover;
        }

        .overlay {
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: linear-gradient(to right, rgba(2, 52, 96, 0.95) 0%, rgba(2, 52, 96, 0.7) 40%, rgba(2, 52, 96, 0) 100%);
            color: white;
            padding: 20px;
            box-sizing: border-box;
            display: flex;
            align-items: center; /* Vertical centering */
            justify-content: flex-start;
        }

        .date-badge {
            background-color: #ff6600;
            color: white;
            font-weight: bold;
            font-size: 18px;
            padding: 8px 12px;
            border-radius: 0 0 10px 0;
            position: absolute;
            top: 0;
            left: 0;
            z-index: 10;
        }

        .metrics-overlay {
            display: flex;
            flex-direction: column;
            gap: 15px;
            /* Position handled by flex container .overlay */
        }

        .metric-item {
            display: flex;
            align-items: center;
            gap: 10px;
            font-size: 18px;
            font-weight: 500;
        }

        .metric-item img {
            width: 24px;
            height: 24px;
            object-fit: contain;
        }

        .data-table {
            width: 100%;
            border-collapse: collapse;
            font-size: 14px;
        }

        .data-table th {
            background-color: #1a2b49;
            color: white;
            padding: 10px;
            text-align: center;
            width: 50%;
        }

        .data-table td {
            padding: 8px 12px;
            border-bottom: 1px solid #eee;
        }
        
        .data-table tr:last-child td {
            border-bottom: none;
        }

        .col-label {
            color: #1a2b49;
            font-weight: 500;
        }

        .col-value {
            text-align: right;
            font-weight: 400;
        }
        
        .table-row {
            display: flex;
        }
        
        .table-half {
            width: 50%;
            border-right: 1px solid #ddd;
        }
        
        .table-half:last-child {
            border-right: none;
        }

        .sub-table {
            width: 100%;
            border-collapse: collapse;
        }
        
        .sub-table td {
             border-bottom: 1px solid #eee;
             padding: 8px;
        }
        
        /* Custom layout to match the reference image's table structure */
        .comparison-table {
            width: 100%;
            border-collapse: collapse;
        }
        
        .comparison-table th {
            background-color: #1a2b49;
            color: white;
            padding: 10px;
            text-align: center;
            border: 1px solid #34495e;
        }
        
        .comparison-table td {
            padding: 8px;
            border: 1px solid #ddd;
            color: #333;
        }
        
        .label-cell {
            text-align: left;
            color: #1a2b49;
        }
        
        .value-cell {
            text-align: right;
        }

    </style>
</head>
<body>

    <div class="container">
        {% for post in posts %}
        <div class="card">
            <div class="image-container">
                <img src="{{ post.image }}" alt="Post Image" class="post-image">
                <div class="date-badge">{{ post.day }}</div>
                <div class="overlay">
                    <div class="metrics-overlay">
                        <div class="metric-item">
                            <img src="icons/views.png" alt="Views">
                            <span>{{ post.total_views }}</span>
                        </div>
                        <div class="metric-item">
                            <img src="icons/alcance.png" alt="Alcance">
                            <span>{{ post.total_alcance }}</span>
                        </div>
                        <div class="metric-item">
                            <img src="icons/interacoes.png" alt="Interações">
                            <span>{{ post.total_interacoes }}</span>
                        </div>
                        <div class="metric-item">
                            <img src="icons/taxa_interaco.png" alt="Taxa">
                            <span>{{ post.total_taxa }}</span>
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
                        <td class="label-cell">Views</td>
                        <td class="value-cell">{{ post.org_views }}</td>
                        <td class="label-cell">Views</td>
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
                        <td class="label-cell">Tx Interação</td>
                        <td class="value-cell">{{ post.org_taxa }}</td>
                        <td class="label-cell">Tx Interação</td>
                        <td class="value-cell">{{ post.paid_taxa }}</td>
                    </tr>
                    <tr>
                        <td colspan="2" style="border:none;"></td>
                        <td class="label-cell">Investimento</td>
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
