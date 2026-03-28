"""
URL Generator Service
Handles URL pattern detection and next page URL generation
"""

import re
import sys
import logging
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse

logger = logging.getLogger(__name__)


class URLGenerator:
    """Generate next page URLs from original URLs"""

    # Common pagination patterns
    PATTERNS = {
        'query_page': r'[?&]page=(\d+)',
        'query_p': r'[?&]p=(\d+)',
        'query_offset': r'[?&]offset=(\d+)',
        'query_start': r'[?&]start=(\d+)',
        'path_page': r'/page[/-](\d+)',
        'path_p': r'/p/(\d+)',
        'path_products': r'/products/page[/-](\d+)',
        'query_custom': r'[?&](\w+)=(\d+)',  # Generic catch-all
    }

    @staticmethod
    def detect_pattern(url: str):
        """Detect pagination pattern in URL"""
        # SAFETY CHECK: url must be a valid string
        logger.debug(f"[URL_PATTERN] detect_pattern called with url={repr(url)} (type: {type(url).__name__})")
        
        if not url:
            logger.warning(f"[URL_PATTERN] url is None or empty, returning 'unknown' pattern")
            return {
                'pattern_type': 'unknown',
                'pattern_regex': None,
                'current_page': 1,
                'match_groups': []
            }
        
        if not isinstance(url, str):
            logger.error(f"[ERROR] url is not a string in detect_pattern: {type(url).__name__}")
            raise TypeError(f"url must be a string, got {type(url).__name__}: {repr(url)}")
        
        try:
            url_lower = url.lower()
            logger.debug(f"[URL_PATTERN] url_lower: {url_lower[:100]}{'...' if len(url_lower) > 100 else ''}")

            # Check each pattern
            for pattern_name, pattern_regex in URLGenerator.PATTERNS.items():
                match = re.search(pattern_regex, url_lower)
                if match:
                    result = {
                        'pattern_type': pattern_name,
                        'pattern_regex': pattern_regex,
                        'current_page': int(match.group(1)) if match.lastindex >= 1 else 1,
                        'match_groups': match.groups()
                    }
                    logger.debug(f"[URL_PATTERN] Detected pattern: {result}")
                    return result

            # No pattern found
            logger.debug(f"[URL_PATTERN] No pattern detected, returning 'unknown'")
            return {
                'pattern_type': 'unknown',
                'pattern_regex': None,
                'current_page': 1,
                'match_groups': []
            }
        except Exception as e:
            logger.error(f"[ERROR] detect_pattern failed: {e}")
            logger.error(f"[ERROR] url: {repr(url)}")
            import traceback
            logger.error(f"[ERROR] Traceback: {traceback.format_exc()}")
            return {
                'pattern_type': 'unknown',
                'pattern_regex': None,
                'current_page': 1,
                'match_groups': []
            }

    @staticmethod
    def generate_next_url(url: str, next_page_number: int, pattern_info: dict = None):
        """Generate next page URL"""
        
        logger.debug(f"[URL_GEN] generate_next_url called with url={repr(url)[:100]}, page={next_page_number}")
        
        # SAFETY CHECK: url must be a valid string
        if not url:
            logger.error(f"[ERROR] url is None or empty in generate_next_url")
            raise ValueError(f"url cannot be None or empty")
        
        if not isinstance(url, str):
            logger.error(f"[ERROR] url is not a string in generate_next_url: {type(url).__name__}")
            raise TypeError(f"url must be a string, got {type(url).__name__}: {repr(url)}")
        
        if pattern_info is None:
            logger.debug(f"[URL_GEN] pattern_info is None, detecting pattern...")
            pattern_info = URLGenerator.detect_pattern(url)

        pattern_type = pattern_info.get('pattern_type')
        logger.debug(f"[URL_GEN] pattern_type: {pattern_type}")

        try:
            # Query parameter patterns
            if 'query_page' in pattern_type or pattern_type == 'query_page':
                result = re.sub(r'([?&]page=)\d+', rf'\g<1>{next_page_number}', url)
                logger.debug(f"[URL_GEN] Applied query_page pattern, result: {result[:100]}")
                return result

            elif 'query_p' in pattern_type or pattern_type == 'query_p':
                result = re.sub(r'([?&]p=)\d+', rf'\g<1>{next_page_number}', url)
                logger.debug(f"[URL_GEN] Applied query_p pattern, result: {result[:100]}")
                return result

            elif 'query_offset' in pattern_type or pattern_type == 'query_offset':
                # For offset-based, we might need to calculate offset
                # Assuming each page has items_per_page (default 10 or 20)
                offset = (next_page_number - 1) * 20
                result = re.sub(r'([?&]offset=)\d+', rf'\g<1>{offset}', url)
                logger.debug(f"[URL_GEN] Applied query_offset pattern, result: {result[:100]}")
                return result

            elif 'query_start' in pattern_type or pattern_type == 'query_start':
                start = (next_page_number - 1) * 20
                result = re.sub(r'([?&]start=)\d+', rf'\g<1>{start}', url)
                logger.debug(f"[URL_GEN] Applied query_start pattern, result: {result[:100]}")
                return result

            # Path-based patterns
            elif 'path_page' in pattern_type or pattern_type == 'path_page':
                result = re.sub(r'/page[/-]\d+', f'/page-{next_page_number}', url)
                logger.debug(f"[URL_GEN] Applied path_page pattern, result: {result[:100]}")
                return result

            elif 'path_p' in pattern_type or pattern_type == 'path_p':
                result = re.sub(r'/p/\d+', f'/p/{next_page_number}', url)
                logger.debug(f"[URL_GEN] Applied path_p pattern, result: {result[:100]}")
                return result

            elif 'path_products' in pattern_type or pattern_type == 'path_products':
                result = re.sub(r'/products/page[/-]\d+', f'/products/page-{next_page_number}', url)
                logger.debug(f"[URL_GEN] Applied path_products pattern, result: {result[:100]}")
                return result

            elif pattern_type == 'query_custom':
                # Generic query parameter replacement
                if pattern_info.get('match_groups'):
                    param_name = pattern_info['match_groups'][0]
                    result = re.sub(rf'([?&]{param_name}=)\d+', rf'\g<1>{next_page_number}', url)
                    logger.debug(f"[URL_GEN] Applied query_custom pattern ({param_name}), result: {result[:100]}")
                    return result

            else:
                # Unknown pattern - try best guess
                # Try common patterns as fallback
                logger.debug(f"[URL_GEN] Unknown pattern, trying common patterns as fallback")
                result = re.sub(r'([?&]page=)\d+', rf'\g<1>{next_page_number}', url)
                if result != url:
                    logger.debug(f"[URL_GEN] Fallback matched query_page pattern")
                    return result

                result = re.sub(r'([?&]p=)\d+', rf'\g<1>{next_page_number}', url)
                if result != url:
                    return result

                # If no substitution worked, append as query parameter
                separator = '&' if '?' in url else '?'
                return f"{url}{separator}page={next_page_number}"

        except Exception as e:
            print(f"[WARNING] Error generating next URL: {str(e)}", file=sys.stderr)
            # Fallback: append page parameter
            separator = '&' if '?' in url else '?'
            return f"{url}{separator}page={next_page_number}"

        return url

    @staticmethod
    def extract_page_number(url: str):
        """Extract current page number from URL"""
        pattern_info = URLGenerator.detect_pattern(url)
        return pattern_info.get('current_page', 1)

    @staticmethod
    def validate_url(url: str):
        """Validate URL format"""
        try:
            result = urlparse(url)
            return all([result.scheme, result.netloc])
        except:
            return False

    @staticmethod
    def get_base_url(url: str):
        """Get base URL without query parameters"""
        parsed = urlparse(url)
        return f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
