import pytest
from unittest.mock import patch, MagicMock
from reddit_persona_backend import RedditPost, RedditScraper


class TestRedditPost:
    """Simple tests for RedditPost class"""
    
    def test_create_post(self):
        """Test 1: Create a basic post"""
        post = RedditPost(
            content="I love programming in Python!",
            title="My Python Journey",
            subreddit="python",
            score=10,
            created_utc=1640995200.0,
            post_type="post",
            permalink="/r/python/comments/abc"
        )
        
        assert post.content == "I love programming in Python!"
        assert post.title == "My Python Journey"
        assert post.subreddit == "python"
        print("✅ Post creation works")
    
    def test_valid_post(self):
        """Test 2: Check if post is valid"""
        post = RedditPost(
            content="This is a good post with enough content",
            title="Good Post",
            subreddit="test",
            score=5,
            created_utc=1640995200.0,
            post_type="post",
            permalink="/test"
        )
        
        assert post.is_valid == True
        print("✅ Valid post detection works")
    
    def test_invalid_post(self):
        """Test 3: Check if invalid post is detected"""
        post = RedditPost(
            content="",  # Empty content should be invalid
            title="Empty Post",
            subreddit="test",
            score=0,
            created_utc=1640995200.0,
            post_type="post",
            permalink="/test"
        )
        
        assert post.is_valid == False
        print("✅ Invalid post detection works")


class TestRedditScraper:
    """Simple tests for RedditScraper class"""
    
    def test_extract_username(self):
        """Test 4: Extract username from Reddit URL"""
        url = "https://www.reddit.com/user/johndoe/"
        username = RedditScraper.extract_username(url)
        
        assert username == "johndoe"
        print("✅ Username extraction works")
    
    def test_extract_username_different_formats(self):
        """Test 5: Extract username from different URL formats"""
        test_cases = [
            ("https://reddit.com/u/alice", "alice"),
            ("www.reddit.com/user/bob", "bob"),
            ("reddit.com/u/charlie/", "charlie")
        ]
        
        for url, expected in test_cases:
            result = RedditScraper.extract_username(url)
            assert result == expected
        
        print("✅ Multiple URL formats work")
    
    def test_invalid_url(self):
        """Test 6: Handle invalid URLs"""
        with pytest.raises(ValueError):
            RedditScraper.extract_username("https://google.com")
        
        print("✅ Invalid URL handling works")
    
    @patch('requests.Session.get')
    def test_fetch_posts_mock(self, mock_get):
        """Test 7: Mock API response (learning mocking)"""
        # Create fake API response
        fake_response = MagicMock()
        fake_response.status_code = 200
        fake_response.json.return_value = {
            'data': {
                'children': [
                    {
                        'data': {
                            'title': 'Test Post',
                            'selftext': 'This is test content',
                            'subreddit': 'test',
                            'score': 5,
                            'created_utc': 1640995200,
                            'permalink': '/test'
                        }
                    }
                ]
            }
        }
        mock_get.return_value = fake_response
        
        # Test the function
        scraper = RedditScraper()
        posts = scraper._fetch_posts("testuser", 5)
        
        assert len(posts) == 1
        assert posts[0].title == "Test Post"
        print("✅ Mocking API responses works")


# Simple fixture example
@pytest.fixture
def sample_post():
    """Fixture: Provides a sample post for tests"""
    return RedditPost(
        content="Sample content for testing",
        title="Sample Title",
        subreddit="test",
        score=1,
        created_utc=1640995200.0,
        post_type="post",
        permalink="/test"
    )


def test_with_fixture(sample_post):
    """Test 8: Using a pytest fixture"""
    assert sample_post.content == "Sample content for testing"
    assert sample_post.subreddit == "test"
    print("✅ Pytest fixtures work")


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v"])