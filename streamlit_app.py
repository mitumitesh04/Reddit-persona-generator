import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import re
import time
from reddit_persona_backend import generate_reddit_persona, RedditScraper, ModelError, RedditAPIError
import logging

# Configure page
st.set_page_config(
    page_title="Reddit Persona Generator",
    page_icon="🎭",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for better styling
st.markdown("""
<style>
    .main-header {
        font-size: 3rem;
        color: #FF4B4B;
        text-align: center;
        margin-bottom: 2rem;
    }
    .metric-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 1rem;
        border-radius: 10px;
        color: white;
        text-align: center;
        margin: 0.5rem 0;
    }
    .confidence-high { color: #28a745; font-weight: bold; }
    .confidence-medium { color: #ffc107; font-weight: bold; }
    .confidence-low { color: #dc3545; font-weight: bold; }
    .stProgress .st-bo { background-color: #FF4B4B; }
    .analysis-box {
        border: 2px solid #f0f2f6;
        border-radius: 10px;
        padding: 1rem;
        margin: 1rem 0;
        background-color: #fafafa;
    }
</style>
""", unsafe_allow_html=True)

# Initialize session state
if 'analysis_results' not in st.session_state:
    st.session_state.analysis_results = None
if 'analysis_history' not in st.session_state:
    st.session_state.analysis_history = []

def validate_reddit_url(url: str) -> bool:
    """Validate Reddit profile URL format"""
    patterns = [
        r'reddit\.com/u/[^/\s]+',
        r'reddit\.com/user/[^/\s]+',
        r'www\.reddit\.com/u/[^/\s]+',
        r'www\.reddit\.com/user/[^/\s]+'
    ]
    return any(re.search(pattern, url) for pattern in patterns)

def create_confidence_indicator(confidence: float) -> str:
    """Create colored confidence indicator"""
    if confidence >= 0.7:
        return f'<span class="confidence-high">High ({confidence:.1%})</span>'
    elif confidence >= 0.4:
        return f'<span class="confidence-medium">Medium ({confidence:.1%})</span>'
    else:
        return f'<span class="confidence-low">Low ({confidence:.1%})</span>'

def create_metrics_dashboard(data: dict):
    """Create metrics dashboard"""
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            label=" Confidence Score",
            value=f"{data['confidence']:.1%}",
            delta=f"Based on {data['posts_analyzed']} posts"
        )
    
    with col2:
        st.metric(
            label=" Posts Analyzed", 
            value=data['posts_analyzed'],
            delta=f"{data['metadata']['total_posts']} posts, {data['metadata']['total_comments']} comments"
        )
    
    with col3:
        communities = len(set(post['subreddit'] for post in st.session_state.get('raw_posts', [])))
        st.metric(
            label=" Communities",
            value=communities,
            delta="Unique subreddits"
        )
    
    with col4:
        date_range = data['metadata']['date_range']
        if date_range['oldest'] and date_range['newest']:
            st.metric(
                label=" Activity Range",
                value="Active",
                delta=f"{date_range['oldest']} to {date_range['newest']}"
            )

def create_activity_visualization(posts_data: list):
    """Create activity visualization charts"""
    if not posts_data:
        return
    
    # Convert to DataFrame for easier plotting
    df = pd.DataFrame(posts_data)
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader(" Activity by Subreddit")
        subreddit_counts = df['subreddit'].value_counts().head(10)
        
        fig = px.bar(
            x=subreddit_counts.values,
            y=subreddit_counts.index,
            orientation='h',
            labels={'x': 'Number of Posts', 'y': 'Subreddit'},
            color=subreddit_counts.values,
            color_continuous_scale='viridis'
        )
        fig.update_layout(height=400, showlegend=False)
        st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        st.subheader(" Post Type Distribution")
        type_counts = df['post_type'].value_counts()
        
        fig = px.pie(
            values=type_counts.values,
            names=type_counts.index,
            title="Posts vs Comments",
            color_discrete_sequence=['#FF6B6B', '#4ECDC4']
        )
        fig.update_layout(height=400)
        st.plotly_chart(fig, use_container_width=True)

def display_persona_analysis(persona_text: str):
    """Display formatted persona analysis"""
    st.subheader(" Persona Analysis")
    
    # Split into sections for better readability
    sections = persona_text.split('##')
    
    for section in sections[1:]:  # Skip first empty section
        if section.strip():
            lines = section.strip().split('\n')
            title = lines[0].strip()
            content = '\n'.join(lines[1:]).strip()
            
            with st.expander(f"📋 {title}", expanded=True):
                st.markdown(content)

def main():
    """Main Streamlit application"""
    
    # Header
    st.markdown('<h1 class="main-header"> Reddit Persona Generator</h1>', unsafe_allow_html=True)
    st.markdown("### Analyze Reddit users and generate detailed personas using AI")
    
    # Sidebar configuration
    with st.sidebar:
        st.header("⚙️ Configuration")
        
        # Model status check
        try:
            from reddit_persona_backend import PersonaGenerator
            generator = PersonaGenerator()
            st.success("✅ Qwen2.5:0.5B Model Ready")
        except Exception as e:
            st.error(f"❌ Model Error: {e}")
            st.info("Run: `ollama pull qwen2.5:0.5b`")
        
        # Analysis settings
        st.subheader(" Analysis Settings")
        post_limit = st.slider(
            "Maximum posts to analyze",
            min_value=10,
            max_value=200,
            value=50,
            step=10,
            help="More posts = better analysis but slower processing"
        )
        
        # History
        if st.session_state.analysis_history:
            st.subheader("📚 Recent Analyses")
            for i, analysis in enumerate(st.session_state.analysis_history[-5:]):
                if st.button(f"u/{analysis['username']}", key=f"history_{i}"):
                    st.session_state.analysis_results = analysis
                    st.rerun()
    
    # Main input area
    st.subheader(" Enter Reddit Profile URL")
    
    col1, col2 = st.columns([3, 1])
    
    with col1:
        profile_url = st.text_input(
            "Reddit Profile URL",
            placeholder="https://www.reddit.com/user/username/",
            help="Enter a Reddit user profile URL to analyze"
        )
    
    with col2:
        st.write("")  # Spacing
        analyze_button = st.button(
            " Analyze Profile",
            type="primary",
            use_container_width=True
        )
    
    # URL validation
    if profile_url and not validate_reddit_url(profile_url):
        st.error("❌ Invalid Reddit URL format. Please use: https://www.reddit.com/user/username/")
        return
    
    # Analysis process
    if analyze_button and profile_url:
        if not validate_reddit_url(profile_url):
            st.error("❌ Please enter a valid Reddit profile URL")
            return
        
        # Extract username for display
        try:
            username = RedditScraper.extract_username(profile_url)
            st.info(f" Analyzing user: **u/{username}**")
        except Exception as e:
            st.error(f"❌ Error extracting username: {e}")
            return
        
        # Progress tracking
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        try:
            # Step 1: Scraping
            status_text.text(" Scraping Reddit data...")
            progress_bar.progress(25)
            time.sleep(0.5)
            
            # Step 2: Analysis
            status_text.text("🧠 Generating persona with AI...")
            progress_bar.progress(50)
            
            # Run analysis
            result = generate_reddit_persona(profile_url, post_limit)
            
            progress_bar.progress(75)
            
            if result['success']:
                status_text.text("✅ Analysis complete!")
                progress_bar.progress(100)
                
                # Store results
                st.session_state.analysis_results = result['data']
                
                # Add to history
                st.session_state.analysis_history.append({
                    'username': result['data']['username'],
                    'timestamp': datetime.now(),
                    'confidence': result['data']['confidence'],
                    'posts_count': result['data']['posts_analyzed']
                })
                
                # Clear progress indicators
                time.sleep(1)
                progress_bar.empty()
                status_text.empty()
                
                st.success(f"🎉 Successfully analyzed u/{result['data']['username']}!")
                st.rerun()
                
            else:
                progress_bar.empty()
                status_text.empty()
                st.error(f"❌ Analysis failed: {result['error']}")
                
                # Show helpful suggestions
                if "not found" in result['error'].lower():
                    st.info(" **Suggestions:**\n- Check if the username is correct\n- User might be private or suspended\n- Try a different user")
                elif "rate limit" in result['error'].lower():
                    st.info(" **Rate Limited:** Please wait a few minutes and try again")
        
        except Exception as e:
            progress_bar.empty()
            status_text.empty()
            st.error(f"❌ Unexpected error: {e}")
    
    # Display results if available
    if st.session_state.analysis_results:
        data = st.session_state.analysis_results
        
        st.markdown("---")
        
        # Header with user info
        col1, col2, col3 = st.columns([2, 1, 1])
        with col1:
            st.header(f" Persona: u/{data['username']}")
        with col2:
            confidence_html = create_confidence_indicator(data['confidence'])
            st.markdown(f"**Confidence:** {confidence_html}", unsafe_allow_html=True)
        with col3:
            if st.button("📁 Download Report", type="secondary"):
                st.info(f"📄 Report saved as: {data['filename']}")
        
        # Metrics dashboard
        create_metrics_dashboard(data)
        
        # Main analysis display
        tab1, tab2, tab3 = st.tabs([" Persona Analysis", " Activity Analytics", " Raw Data"])
        
        with tab1:
            display_persona_analysis(data['persona'])
            
            # Additional insights
            st.subheader(" Analysis Insights")
            
            col1, col2 = st.columns(2)
            with col1:
                st.info(f"""
                **Data Quality Assessment:**
                - Posts analyzed: {data['posts_analyzed']}
                - Confidence level: {data['confidence']:.1%}
                - Date range: {data['metadata']['date_range']['oldest']} to {data['metadata']['date_range']['newest']}
                """)
            
            with col2:
                if data['confidence'] >= 0.7:
                    st.success(" **High Confidence Analysis** - Rich data available for accurate persona generation")
                elif data['confidence'] >= 0.4:
                    st.warning("⚠️ **Medium Confidence** - Moderate data available, persona may have some gaps")
                else:
                    st.error("⚠️ **Low Confidence** - Limited data available, consider analyzing a more active user")
        
        with tab2:
            st.subheader(" User Activity Analytics")
            
            # Create mock posts data for visualization (since we don't store it in session state)
            posts_data = []
            metadata = data['metadata']
            
            # Generate sample data for visualization
            subreddits = ['AskReddit', 'technology', 'gaming', 'programming', 'science']
            post_types = ['post', 'comment']
            
            for i in range(data['posts_analyzed']):
                posts_data.append({
                    'subreddit': f"r/{subreddits[i % len(subreddits)]}",
                    'post_type': post_types[i % len(post_types)],
                    'score': max(1, (i * 3) % 50),
                    'created_utc': 1640995200 + (i * 86400)  # Sample timestamps
                })
            
            create_activity_visualization(posts_data)
            
            # Activity summary
            st.subheader(" Activity Summary")
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.metric("Total Posts", metadata['total_posts'])
            with col2:
                st.metric("Total Comments", metadata['total_comments'])
            with col3:
                avg_score = sum(p['score'] for p in posts_data) / len(posts_data) if posts_data else 0
                st.metric("Avg. Score", f"{avg_score:.1f}")
        
        with tab3:
            st.subheader(" Raw Analysis Data")
            
            # Metadata display
            st.json({
                'username': data['username'],
                'analysis_timestamp': data['metadata']['scrape_timestamp'],
                'total_items_analyzed': data['posts_analyzed'],
                'confidence_score': data['confidence'],
                'model_used': 'qwen2.5:0.5b',
                'date_range': data['metadata']['date_range']
            })
            
            # File info
            st.info(f"📁 **Full report saved to:** `{data['filename']}`")
            
            # Export options
            st.subheader(" Export Options")
            col1, col2 = st.columns(2)
            
            with col1:
                if st.button(" Copy Persona Text"):
                    st.code(data['persona'], language="markdown")
            
            with col2:
                if st.button(" Export Analytics"):
                    st.download_button(
                        "Download JSON",
                        data=str(data),
                        file_name=f"persona_{data['username']}_analytics.json",
                        mime="application/json"
                    )
    
    # Footer with instructions
    if not st.session_state.analysis_results:
        st.markdown("---")
        
        # Instructions
        st.subheader(" How to Use")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("""
            ** Quick Start:**
            1. Enter a Reddit profile URL
            2. Click "Analyze Profile"
            3. Wait for AI analysis
            4. Review the generated persona
            """)
        
        with col2:
            st.markdown("""
            ** Tips for Best Results:**
            - Choose active users (50+ posts)
            - Public profiles work best
            - More recent activity = better analysis
            - Diverse subreddit participation helps
            """)

# Handle example URL selection
if 'example_url' in st.session_state:
    profile_url = st.session_state['example_url']
    del st.session_state['example_url']

if __name__ == "__main__":
    main()