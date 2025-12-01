import logging
import os

import psycopg2
from psycopg2.extras import RealDictCursor

logger = logging.getLogger(__name__)


class PostgresMemoryService:
    def __init__(self):
        self.connection_params = {
            "host": os.getenv("DB_HOST", "localhost"),
            "database": os.getenv("DB_NAME", "reviewbot"),
            "user": os.getenv("DB_USER", "postgres"),
            "password": os.getenv("DB_PASSWORD", "postgres"),
            "port": os.getenv("DB_PORT", "5432"),
            "connect_timeout": 10,
        }
        self._init_schema()

    def _get_connection(self):
        """Get database connection"""
        return psycopg2.connect(**self.connection_params)

    def _init_schema(self):
        """Initialize database schema"""
        import time

        max_retries = 5

        for attempt in range(max_retries):
            try:
                with self._get_connection() as conn:
                    with conn.cursor() as cur:
                        cur.execute("""
                            CREATE TABLE IF NOT EXISTS mr_reviews (
                                mr_iid INTEGER,
                                project_id INTEGER,
                                diff_text TEXT,
                                final_review_text TEXT,
                                review_comment_id INTEGER,
                                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                                PRIMARY KEY (project_id, mr_iid)
                            )
                        """)
                        conn.commit()
                logger.info("Database schema initialized")
                return
            except Exception as e:
                logger.warning(f"Database connection attempt {attempt + 1} failed: {e}")
                if attempt < max_retries - 1:
                    time.sleep(2)
                else:
                    logger.error(
                        f"Failed to initialize schema after {max_retries} attempts: {e}"
                    )

    def save_review_context(
        self,
        project_id: int,
        mr_iid: int,
        diff_text: str,
        final_review_text: str,
        review_comment_id: int | None = None,
    ) -> bool:
        """Save review context to database"""
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO mr_reviews (project_id, mr_iid, diff_text, final_review_text, review_comment_id)
                        VALUES (%s, %s, %s, %s, %s)
                        ON CONFLICT (project_id, mr_iid)
                        DO UPDATE SET
                            diff_text = EXCLUDED.diff_text,
                            final_review_text = EXCLUDED.final_review_text,
                            review_comment_id = EXCLUDED.review_comment_id
                    """,
                        (
                            project_id,
                            mr_iid,
                            diff_text,
                            final_review_text,
                            review_comment_id,
                        ),
                    )
                    conn.commit()
            logger.info(f"Saved review context for MR !{mr_iid}")
            return True
        except Exception as e:
            logger.error(f"Failed to save review context: {e}")
            return False

    def load_review_context(
        self, project_id: int, mr_iid: int
    ) -> tuple[str | None, str | None]:
        """Load review context from database"""
        try:
            with self._get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute(
                        """
                        SELECT diff_text, final_review_text
                        FROM mr_reviews
                        WHERE project_id = %s AND mr_iid = %s
                    """,
                        (project_id, mr_iid),
                    )

                    result = cur.fetchone()
                    if result:
                        return result["diff_text"], result["final_review_text"]
                    return None, None
        except Exception as e:
            logger.error(f"Failed to load review context: {e}")
            return None, None

    def health_check(self) -> bool:
        """Check if database connection is healthy"""
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1")
                    return True
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            return False
