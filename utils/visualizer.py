import os
import time
import matplotlib
matplotlib.use('Agg')  # Set headless backend
import matplotlib.pyplot as plt
import seaborn as sns
from database.client import supabase_admin

def generate_velocity_chart(phone_number: str, categories: list, spent_values: list, limit_values: list, proposed_limits: list = None) -> str:
    """
    Generates a horizontal bar chart visualizing current spending vs limits,
    with optional proposed limits for damage control rebalancing.
    Uploads the generated chart to Supabase Storage and returns the public URL.
    """
    # Use standard seaborn/matplotlib style configurations
    sns.set_theme(style="dark")
    
    # Setup dark mode premium colors
    plt.rcParams['text.color'] = '#E2E8F0'
    plt.rcParams['axes.labelcolor'] = '#E2E8F0'
    plt.rcParams['xtick.color'] = '#94A3B8'
    plt.rcParams['ytick.color'] = '#94A3B8'
    plt.rcParams['figure.facecolor'] = '#0F172A'  # Slate-900
    plt.rcParams['axes.facecolor'] = '#1E293B'   # Slate-800
    
    fig, ax = plt.subplots(figsize=(8, 4.5), dpi=150)
    
    y_positions = range(len(categories))
    bar_height = 0.4
    
    # 1. Plot the current monthly limits
    ax.barh([y + bar_height/2 for y in y_positions], limit_values, height=bar_height, 
            color='#475569', label='Original Monthly Limit', alpha=0.6, edgecolor='#64748B')
            
    # 2. Plot current spending
    spent_colors = []
    for s, l in zip(spent_values, limit_values):
        if s > l:
            spent_colors.append('#EF4444')  # Red-500 (Breached)
        else:
            spent_colors.append('#10B981')  # Emerald-500 (Safe)
            
    ax.barh([y - bar_height/2 for y in y_positions], spent_values, height=bar_height, 
            color=spent_colors, label='Current Spent', edgecolor='#34D399', alpha=0.95)
            
    # 3. Plot proposed limits (if rebalancing occurred)
    if proposed_limits:
        for idx, y in enumerate(y_positions):
            prop_lim = proposed_limits[idx]
            orig_lim = limit_values[idx]
            if prop_lim != orig_lim:
                # Draw a vertical dashed line on the specific category bar to show new boundary
                ax.vlines(x=prop_lim, ymin=y - bar_height, ymax=y + bar_height, 
                          color='#F59E0B', colors='#F59E0B', linestyles='dashed', linewidth=2,
                          label='Proposed Limit' if idx == 0 else "")
                
                # Add text label for the proposed limit
                ax.text(prop_lim + (max(limit_values) * 0.01), y, f"New: ${int(prop_lim)}", 
                        color='#F59E0B', va='center', fontweight='bold', fontsize=8)

    # Decorate plot
    ax.set_yticks(y_positions)
    ax.set_yticklabels(categories, fontsize=10, fontweight='bold')
    ax.set_xlabel('Amount ($)', fontsize=10, fontweight='bold', labelpad=10)
    ax.set_title('SpendWise: Spending Velocity and Rebalancing Plan', fontsize=12, fontweight='bold', pad=15, color='#F8FAFC')
    
    # Annotate bar values (Spent / Limit)
    for idx, (s, l) in enumerate(zip(spent_values, limit_values)):
        label_text = f"${int(s)} / ${int(l)}"
        ax.text(max(s, l) + (max(limit_values) * 0.02), idx - bar_height/2, label_text, 
                color='#F1F5F9' if s <= l else '#FDA4AF', va='center', fontsize=9, fontweight='bold')
                
    # Formatting grid and spines
    ax.grid(True, axis='x', linestyle=':', alpha=0.3, color='#94A3B8')
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['left'].set_color('#475569')
    ax.spines['bottom'].set_color('#475569')
    
    ax.legend(loc='lower right', facecolor='#1E293B', edgecolor='#475569', labelcolor='#E2E8F0', fontsize=9)
    plt.tight_layout()
    
    # Save the plot locally
    clean_phone = phone_number.replace('+', '').replace(' ', '')
    filename = f"chart_{clean_phone}_{int(time.time())}.png"
    local_path = os.path.abspath(filename)
    
    try:
        fig.savefig(local_path, format='png', facecolor=fig.get_facecolor(), edgecolor='none', bbox_inches='tight')
        plt.close(fig)
        
        # Upload to Supabase Storage
        storage_path = f"{clean_phone}/{filename}"
        with open(local_path, 'rb') as f:
            supabase_admin.storage.from_("charts").upload(
                path=storage_path,
                file=f,
                file_options={"content-type": "image/png"}
            )
            
        # Get public URL
        public_url = supabase_admin.storage.from_("charts").get_public_url(storage_path)
        return public_url
    finally:
        # Clean up local file
        if os.path.exists(local_path):
            os.remove(local_path)
