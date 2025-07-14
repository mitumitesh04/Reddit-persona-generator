# reddit_persona_backend.py
"""
Optimized Reddit User Persona Generator Backend
Clean architecture with proper error handling and logging
"""

import requests
import json
import time
import re
import os
from urllib.parse import urlparse
from dataclasses import dataclass, asdict
from typing import List, Dict, Optional, Tuple
from datetime import datetime
import logging
import ollama
from concurrent.futures import ThreadPoolExecutor, as_completed

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@dataclass
class RedditPost:
    """Immutable Reddit post/comment data structure"""
    content: str
    title: str
    subreddit: str
    score: int
    created_utc: float
    post_type: str
    permalink: str
    
    def __post_init__(self):
        # Clean and validate data
        self.content = self.content.strip()
        self.title = self.title.strip()
        self.subreddit = self.subreddit.strip()
    
    @property
    def created_date(self) -> str:
        """Human readable creation date"""
        return datetime.fromtimestamp(self.created_utc).strftime('%Y-%m-%d %H:%M')
    
    @property
    def is_valid(self) -> bool:
        """Check if post has meaningful content"""
        return (
            len(self.content) > 10 and 
            self.content.lower() not in ['[deleted]', '[removed]', 'deleted', 'removed']
        )

@dataclass
class UserPersona:
    """Structured user persona with metadata"""
    username: str
    demographics: Dict[str, str]
    interests: List[str]
    personality_traits: List[str]
    values_beliefs: List[str]
    online_behavior: Dict[str, str]
    goals_motivations: List[str]
    pain_points: List[str]
    technical_proficiency: str
    communication_style: str
    confidence_score: float
    analysis_metadata: Dict[str, any]

class RedditAPIError(Exception):
    """Custom exception for Reddit API errors"""
    pass

class ModelError(Exception):
    """Custom exception for LLM model errors"""
    pass

class RedditScraper:
    """Optimized Reddit data scraper with better error handling"""
    
    def __init__(self, timeout: int = 30, max_retries: int = 3):
        self.timeout = timeout
        self.max_retries = max_retries
        self.session = self._create_session()
        self.rate_limit_delay = 2  # seconds between requests
    
    def _create_session(self) -> requests.Session:
        """Create configured requests session"""
        session = requests.Session()
        session.headers.update({
            'User-Agent': 'PersonaGenerator/2.0 (Educational Research Tool)',
            'Accept': 'application/json',
            'Accept-Language': 'en-US,en;q=0.9'
        })
        session.timeout = self.timeout
        return session
    
    @staticmethod
    def extract_username(profile_url: str) -> str:
        """Extract and validate username from Reddit URL"""
        if not profile_url or not isinstance(profile_url, str):
            raise ValueError("Invalid profile URL provided")
        
        # Handle different URL formats
        url_patterns = [
            r'reddit\.com/u/([^/\?]+)',
            r'reddit\.com/user/([^/\?]+)',
            r'www\.reddit\.com/u/([^/\?]+)',
            r'www\.reddit\.com/user/([^/\?]+)'
        ]
        
        for pattern in url_patterns:
            match = re.search(pattern, profile_url)
            if match:
                username = match.group(1)
                if username and len(username) > 0:
                    return username
        
        raise ValueError(f"Could not extract valid username from URL: {profile_url}")
    
    def _make_request(self, url: str, params: Dict = None) -> Dict:
        """Make HTTP request with retry logic"""
        for attempt in range(self.max_retries):
            try:
                logger.info(f"Making request to {url} (attempt {attempt + 1})")
                response = self.session.get(url, params=params)
                
                if response.status_code == 200:
                    return response.json()
                elif response.status_code == 429:
                    wait_time = 2 ** attempt * 5  # Exponential backoff
                    logger.warning(f"Rate limited. Waiting {wait_time} seconds...")
                    time.sleep(wait_time)
                else:
                    logger.warning(f"HTTP {response.status_code} for {url}")
                    
            except requests.exceptions.RequestException as e:
                logger.error(f"Request failed: {e}")
                if attempt == self.max_retries - 1:
                    raise RedditAPIError(f"Failed to fetch data after {self.max_retries} attempts")
                time.sleep(2 ** attempt)
        
        raise RedditAPIError("Max retries exceeded")
    
    def _fetch_posts(self, username: str, limit: int) -> List[RedditPost]:
        """Fetch user posts with error handling"""
        url = f"https://www.reddit.com/user/{username}/submitted.json"
        
        try:
            data = self._make_request(url, {'limit': limit})
            posts = []
            
            for item in data.get('data', {}).get('children', []):
                post_data = item.get('data', {})
                
                content = post_data.get('selftext', '') or post_data.get('title', '')
                post = RedditPost(
                    content=content,
                    title=post_data.get('title', ''),
                    subreddit=post_data.get('subreddit', ''),
                    score=post_data.get('score', 0),
                    created_utc=post_data.get('created_utc', 0),
                    post_type='post',
                    permalink=f"https://reddit.com{post_data.get('permalink', '')}"
                )
                
                if post.is_valid:
                    posts.append(post)
            
            return posts
            
        except Exception as e:
            logger.error(f"Error fetching posts: {e}")
            return []
    
    def _fetch_comments(self, username: str, limit: int) -> List[RedditPost]:
        """Fetch user comments with error handling"""
        url = f"https://www.reddit.com/user/{username}/comments.json"
        
        try:
            data = self._make_request(url, {'limit': limit})
            comments = []
            
            for item in data.get('data', {}).get('children', []):
                comment_data = item.get('data', {})
                
                content = comment_data.get('body', '')
                comment = RedditPost(
                    content=content,
                    title=comment_data.get('link_title', ''),
                    subreddit=comment_data.get('subreddit', ''),
                    score=comment_data.get('score', 0),
                    created_utc=comment_data.get('created_utc', 0),
                    post_type='comment',
                    permalink=f"https://reddit.com{comment_data.get('permalink', '')}"
                )
                
                if comment.is_valid:
                    comments.append(comment)
            
            return comments
            
        except Exception as e:
            logger.error(f"Error fetching comments: {e}")
            return []
    
    def scrape_user_data(self, profile_url: str, limit: int = 50) -> Tuple[List[RedditPost], Dict]:
        """Main scraping method with parallel fetching"""
        username = self.extract_username(profile_url)
        logger.info(f"Scraping data for user: {username}")
        
        # Parallel fetching for better performance
        with ThreadPoolExecutor(max_workers=2) as executor:
            post_future = executor.submit(self._fetch_posts, username, limit // 2)
            comment_future = executor.submit(self._fetch_comments, username, limit // 2)
            
            posts = post_future.result()
            comments = comment_future.result()
        
        # Combine and sort by recency
        all_posts = posts + comments
        all_posts.sort(key=lambda x: x.created_utc, reverse=True)
        
        # Create metadata
        metadata = {
            'username': username,
            'total_posts': len(posts),
            'total_comments': len(comments),
            'total_items': len(all_posts),
            'scrape_timestamp': datetime.now().isoformat(),
            'date_range': {
                'oldest': min(all_posts, key=lambda x: x.created_utc).created_date if all_posts else None,
                'newest': max(all_posts, key=lambda x: x.created_utc).created_date if all_posts else None
            }
        }
        
        logger.info(f"Successfully scraped {len(all_posts)} items for {username}")
        return all_posts, metadata

class PersonaGenerator:
    """Optimized persona generator with better prompt engineering"""
    
    def __init__(self, model_name: str = "qwen2.5:0.5b"):
        self.model_name = model_name
        self.validate_model()
    
    def validate_model(self):
        """Validate model availability with better error handling"""
        try:
            # Test model with minimal request
            response = ollama.generate(
                model=self.model_name,
                prompt="Hi",
                options={'num_predict': 1}
            )
            logger.info(f"Model {self.model_name} is available")
        except Exception as e:
            raise ModelError(f"Model {self.model_name} not available. Error: {e}")
    
    def _create_structured_prompt(self, posts: List[RedditPost], metadata: Dict) -> str:
        """Create optimized prompt with better structure"""
        
        # Analyze posting patterns
        subreddits = {}
        total_score = 0
        
        for post in posts:
            subreddits[post.subreddit] = subreddits.get(post.subreddit, 0) + 1
            total_score += post.score
        
        top_subreddits = sorted(subreddits.items(), key=lambda x: x[1], reverse=True)[:5]
        
        # Create focused content sample
        content_sample = ""
        for i, post in enumerate(posts[:15]):  # Optimized for 0.5B model
            content_sample += f"\n[{i+1}] {post.post_type.upper()} in r/{post.subreddit}\n"
            if post.title:
                content_sample += f"Title: {post.title}\n"
            content_sample += f"Content: {post.content[:250]}{'...' if len(post.content) > 250 else ''}\n"
            content_sample += f"Score: {post.score} | Date: {post.created_date}\n"
        
        prompt = f"""Analyze this Reddit user to create a detailed persona.

USER: {metadata['username']}
ACTIVITY: {metadata['total_posts']} posts, {metadata['total_comments']} comments
TOP COMMUNITIES: {', '.join([f"r/{sub}({count})" for sub, count in top_subreddits])}
AVERAGE SCORE: {total_score/len(posts) if posts else 0:.1f}

RECENT CONTENT:
{content_sample}

Create a structured persona analysis:

## DEMOGRAPHICS
- Age range and generation
- Location/region indicators  
- Education level
- Occupation/field

## INTERESTS & HOBBIES
- Primary interests (rank by evidence)
- Hobbies and activities
- Subject matter expertise

## PERSONALITY PROFILE
- Communication style
- Social tendencies
- Emotional patterns

## DIGITAL BEHAVIOR
- Posting patterns
- Community engagement
- Content preferences
- Online persona vs. real self


For each insight, reference specific evidence with post numbers [1], [2], etc.
Rate your confidence (High/Medium/Low) for each major conclusion."""

        return prompt
    
    def generate_persona(self, posts: List[RedditPost], metadata: Dict) -> Tuple[str, float]:
        """Generate persona with confidence scoring"""
        if not posts:
            return "Insufficient data for analysis.", 0.0
        
        prompt = self._create_structured_prompt(posts, metadata)
        
        try:
            logger.info("Generating persona with LLM...")
            response = ollama.generate(
                model=self.model_name,
                prompt=prompt,
                options={
                    'temperature': 0.6,
                    'top_p': 0.9,
                    'num_predict': 1500,
                    'stop': ['</s>', '<|endoftext|>', '---END---']
                }
            )
            
            persona_text = response['response']
            
            # Calculate confidence based on data quality
            confidence = self._calculate_confidence(posts, metadata)
            
            return persona_text, confidence
            
        except Exception as e:
            logger.error(f"Error generating persona: {e}")
            raise ModelError(f"Failed to generate persona: {e}")
    
    def _calculate_confidence(self, posts: List[RedditPost], metadata: Dict) -> float:
        """Calculate confidence score based on data quality"""
        score = 0.0
        
        # Data quantity (0-40 points)
        post_count = len(posts)
        if post_count >= 50:
            score += 40
        elif post_count >= 20:
            score += 30
        elif post_count >= 10:
            score += 20
        else:
            score += post_count
        
        # Content quality (0-30 points)
        avg_length = sum(len(post.content) for post in posts) / len(posts) if posts else 0
        if avg_length > 100:
            score += 30
        elif avg_length > 50:
            score += 20
        else:
            score += 10
        
        # Diversity (0-20 points)
        unique_subreddits = len(set(post.subreddit for post in posts))
        if unique_subreddits >= 10:
            score += 20
        elif unique_subreddits >= 5:
            score += 15
        else:
            score += unique_subreddits * 2
        
        # Engagement (0-10 points)
        avg_score = sum(post.score for post in posts) / len(posts) if posts else 0
        if avg_score > 10:
            score += 10
        elif avg_score > 5:
            score += 7
        elif avg_score > 0:
            score += 5
        
        return min(score / 100.0, 1.0)  # Normalize to 0-1

class PersonaManager:
    """Manages persona generation and file operations"""
    
    @staticmethod
    def save_persona(username: str, persona_text: str, posts: List[RedditPost], 
                    metadata: Dict, confidence: float) -> str:
        """Save comprehensive persona analysis"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"persona_{username}_{timestamp}.txt"
        
        with open(filename, 'w', encoding='utf-8') as f:
            f.write("🎭 REDDIT USER PERSONA ANALYSIS\n")
            f.write("=" * 70 + "\n")
            f.write(f"Username: u/{username}\n")
            f.write(f"Analysis Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Data Points: {metadata['total_items']} posts/comments\n")
            f.write(f"Confidence Score: {confidence:.2%}\n")
            f.write(f"Model: Qwen2.5:0.5B\n")
            f.write("=" * 70 + "\n\n")
            
            f.write("📊 PERSONA ANALYSIS\n")
            f.write("-" * 50 + "\n")
            f.write(persona_text)
            
            f.write(f"\n\n📈 DATA SUMMARY\n")
            f.write("-" * 50 + "\n")
            f.write(f"Posts: {metadata['total_posts']}\n")
            f.write(f"Comments: {metadata['total_comments']}\n")
            f.write(f"Date Range: {metadata['date_range']['oldest']} to {metadata['date_range']['newest']}\n")
            
            # Top subreddits
            subreddit_counts = {}
            for post in posts:
                subreddit_counts[post.subreddit] = subreddit_counts.get(post.subreddit, 0) + 1
            
            f.write(f"\nTop Communities:\n")
            for sub, count in sorted(subreddit_counts.items(), key=lambda x: x[1], reverse=True)[:10]:
                f.write(f"  r/{sub}: {count} posts\n")
            
            f.write(f"\n\n📝 SUPPORTING EVIDENCE\n")
            f.write("-" * 50 + "\n")
            for i, post in enumerate(posts[:20]):
                f.write(f"\n[{i+1}] {post.post_type.upper()} | r/{post.subreddit} | {post.created_date}\n")
                if post.title:
                    f.write(f"Title: {post.title}\n")
                f.write(f"Content: {post.content[:300]}{'...' if len(post.content) > 300 else ''}\n")
                f.write(f"Score: {post.score} | Link: {post.permalink}\n")
        
        return filename

# Main API function for easy integration
def generate_reddit_persona(profile_url: str, limit: int = 50) -> Dict:
    """
    Main function to generate Reddit user persona
    
    Args:
        profile_url: Reddit profile URL
        limit: Maximum posts to analyze
    
    Returns:
        Dictionary with persona data and metadata
    """
    try:
        # Initialize components
        scraper = RedditScraper()
        generator = PersonaGenerator()
        
        # Scrape data
        posts, metadata = scraper.scrape_user_data(profile_url, limit)
        
        if not posts:
            return {
                'success': False,
                'error': 'No posts found or user may be private',
                'data': None
            }
        
        # Generate persona
        persona_text, confidence = generator.generate_persona(posts, metadata)
        
        # Save results
        username = scraper.extract_username(profile_url)
        filename = PersonaManager.save_persona(username, persona_text, posts, metadata, confidence)
        
        return {
            'success': True,
            'data': {
                'username': username,
                'persona': persona_text,
                'confidence': confidence,
                'metadata': metadata,
                'filename': filename,
                'posts_analyzed': len(posts)
            },
            'error': None
        }
        
    except Exception as e:
        logger.error(f"Error in persona generation: {e}")
        return {
            'success': False,
            'error': str(e),
            'data': None
        }