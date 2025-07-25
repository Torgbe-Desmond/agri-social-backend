from sqlalchemy import text

# Get user profile details
_get_user_profile = text("""
    SELECT 
        u.id,
        u.username,
        u.email,
        u.created_at,
        u.city,
        u.firstname,
        u.lastname,
        u.reference_id,
        COALESCE(u.user_image, '') AS user_image,
        (
            SELECT COUNT(*) FROM followers WHERE follower_id = u.id
        ) AS following,
        (
            SELECT COUNT(*) FROM followers WHERE following_id = u.id
        ) AS followers
    FROM users u
    WHERE u.id = :userId
""")

# View notifications (mark as read)
_view_notifications = text("""
    UPDATE notifications 
    SET is_read = 1
    WHERE id IN (
        SELECT value FROM STRING_SPLIT(:NotificationIds, ',')
    )
""")

# Get saved posts
_get_saved_posts = text("""
SELECT 
    p.id AS post_id,
    p.content,
    p.created_at,
    p.user_id,
    p.has_video,
    COALESCE((SELECT user_image FROM users WHERE id = p.user_id), '') AS user_image,
    (SELECT COUNT(*) FROM post_likes WHERE post_id = p.id) AS likes,
    (SELECT COUNT(*) FROM saved_posts WHERE post_id = p.id) AS saved,
    (SELECT COUNT(*) FROM comments WHERE post_id = p.id) AS comments,
    (SELECT image_url FROM post_images WHERE post_id = p.id LIMIT 1) AS images,
    (SELECT video_url FROM post_videos WHERE post_id = p.id LIMIT 1) AS videos,
    (SELECT username FROM users WHERE id = p.user_id) AS username
FROM posts p
WHERE p.id IN (
    SELECT unnest(string_to_array(:PostIds, ',')::uuid[])
)
ORDER BY p.created_at DESC
OFFSET :offset
LIMIT :limit;
""")

# Get product history by user
_get_product_history = text("""
    SELECT 
        p.id AS product_id,
        p.title,
        p.description,
        p.price,
        p.unit,
        p.user_id,
        COALESCE(STRING_AGG(pi.image_url, ','), '') AS product_images,
        p.created_at
    FROM products p
    LEFT JOIN product_images pi ON pi.product_id = p.id
    WHERE p.user_id = :user_id
    GROUP BY 
        p.id, p.title, p.description, p.price, p.unit, p.user_id, p.created_at
""")

# Get product by ID
_get_product = text("""
    SELECT 
        p.id AS product_id,
        p.title,
        p.description,
        p.price,
        p.unit,
        p.user_id,
        p.created_at,
        COALESCE(STRING_AGG(pi.image_url, ','), '') AS product_images,
        COALESCE(u.contact, '') AS contact,
        COALESCE(u.city, '') AS city
    FROM products p
    LEFT JOIN product_images pi ON pi.product_id = p.id
    LEFT JOIN users u ON u.id = p.user_id
    WHERE p.id = :product_id
    GROUP BY 
        p.id, p.title, p.description, p.price, p.unit, p.user_id, p.created_at, u.contact, u.city
""")

# Get prediction history
_get_prediction_history = text("""
    SELECT 
        p.id AS prediction_id,
        p.created_at,
        d.image_url,
        d.prediction_label
    FROM predictions p
    LEFT JOIN prediction_details d ON p.id = d.prediction_id
    WHERE p.user_id = :user_id
    FOR JSON PATH
""")

# Get post history
_get_post_history = text("""
    SELECT 
        p.id AS post_id,
        p.content,
        p.created_at,
        p.user_id,
        p.has_video,
        COALESCE((SELECT user_image FROM users WHERE id = p.user_id), '') AS user_image,
        (SELECT COUNT(*) FROM post_likes WHERE post_id = p.id) AS likes,
        (SELECT COUNT(*) FROM saved_posts WHERE post_id = p.id) AS saved,
        (SELECT COUNT(*) FROM comments WHERE post_id = p.id) AS comments,
        COALESCE((SELECT STRING_AGG(image_url, ',') FROM post_images WHERE post_id = p.id), '') AS images,
        COALESCE((SELECT STRING_AGG(tag_name, ',') FROM tags WHERE post_id = p.id), '') AS tags,
        COALESCE((SELECT STRING_AGG(video_url, ',') FROM post_videos WHERE post_id = p.id), '') AS videos,
        (SELECT username FROM users WHERE id = p.user_id) AS username
    FROM posts p
    WHERE p.user_id = :user_id 
    ORDER BY p.created_at DESC
    OFFSET :offset
    LIMIT :limit;
    
""")

# Get post by ID
_get_post = text("""
    SELECT 
        p.id AS post_id,
        p.content,
        p.created_at,
        p.user_id,
        p.has_video,
        COALESCE((SELECT user_image FROM users WHERE id = p.user_id), '') AS user_image,
        (SELECT COUNT(*) FROM post_likes WHERE post_id = p.id) AS likes,
        (SELECT COUNT(*) FROM saved_posts WHERE post_id = p.id) AS saved,
        (SELECT COUNT(*) FROM comments WHERE post_id = p.id) AS comments,
        COALESCE((SELECT STRING_AGG(image_url, ',') FROM post_images WHERE post_id = p.id), '') AS images,
        COALESCE((SELECT STRING_AGG(tag_name, ',') FROM tags WHERE post_id = p.id), '') AS tags,
        COALESCE((SELECT STRING_AGG(video_url, ',') FROM post_videos WHERE post_id = p.id), '') AS videos,
        (SELECT username FROM users WHERE id = p.user_id) AS username
    FROM posts p
    WHERE p.id = :PostId
""")

# Get notifications by user ID
_get_notifications_by_user_id = text("""
    SELECT 
        n.id,
        n.user_id,
        n.actor_id,
        n.type,
        n.entity_type,
        n.entity_id,
        n.action_id,
        n.message,
        COALESCE((SELECT user_image FROM users WHERE id = n.actor_id), '') AS user_image,
        COALESCE((SELECT username FROM users WHERE id = n.actor_id), '') AS username,
        COALESCE((
               SELECT STRING_AGG(image_url, ',') 
               FROM post_images 
               WHERE post_id = n.entity_id::uuid
           ), '') AS images,
        COALESCE((
               SELECT STRING_AGG(video_url, ',') 
               FROM post_videos 
               WHERE post_id = n.entity_id::uuid
           ), '') AS videos,        
        n.is_read,
        n.created_at
    FROM notifications n
    INNER JOIN users u ON n.user_id = u.id
    WHERE n.user_id = :user_id
    ORDER BY created_at DESC
    OFFSET :offset ROWS
    FETCH NEXT :limit ROWS ONLY
""")

# Get comments for a post or comment
_get_comments = text("""
    SELECT 
        c.id,
        c.post_id,
        c.user_id,
        c.content,
        c.created_at,
        COALESCE(u.user_image, '') AS user_image,
        c.parent_id,
        (SELECT COUNT(*) FROM comments WHERE parent_id = c.id) AS replies,
        (SELECT COUNT(*) FROM comment_likes WHERE comment_id = c.id) AS likes,
        u.username
    FROM comments c
    LEFT JOIN users u ON u.id = c.user_id
    WHERE c.post_id = :ParentOrPostId OR c.parent_id = :ParentOrPostId
    ORDER BY c.created_at ASC
""")

# Get replies for a parent comment
_get_comment_of_parent = text("""
    SELECT 
        c.post_id,
        c.parent_id,
        c.user_id,
        c.content,
        c.created_at,
        (SELECT username FROM users WHERE id = c.user_id) AS username
    FROM comments c
    WHERE c.parent_id = :ParentId
""")

# Get a single comment
_get_comment = text("""
    SELECT 
        c.id,
        c.post_id,
        c.user_id,
        c.content,
        c.created_at,
        COALESCE(u.user_image, '') AS user_image,
        u.username,
        c.parent_id,
        (SELECT COUNT(*) FROM comments WHERE parent_id = c.id) AS replies,
        (SELECT COUNT(*) FROM comment_likes WHERE comment_id = c.id) AS likes
    FROM comments c
    LEFT JOIN users u ON u.id = c.user_id
    WHERE c.id = :comment_id
""")

# Get all products
_get_all_products = text("""
    SELECT 
        p.id AS product_id,
        p.title,
        p.description,
        p.price,
        p.unit,
        p.user_id,
        COALESCE(STRING_AGG(pi.image_url, ','), '') AS product_images,
        p.created_at
    FROM products p
    LEFT JOIN product_images pi ON p.id = pi.product_id
    GROUP BY 
        p.id, p.title, p.description, p.price, p.unit, p.user_id, p.created_at
    ORDER BY p.created_at DESC
    OFFSET :offset ROWS
    FETCH NEXT :limit ROWS ONLY
""")

# Get all posts
_get_all_posts = text("""
    SELECT 
        p.id AS post_id,
        p.content,
        p.created_at,
        p.user_id,
        p.has_video,
        COALESCE((SELECT user_image FROM users WHERE id = p.user_id), '') AS user_image,
        (SELECT COUNT(*) FROM post_likes WHERE post_id = p.id) AS likes,
        (SELECT COUNT(*) FROM saved_posts WHERE post_id = p.id) AS saved,
        (SELECT COUNT(*) FROM comments WHERE post_id = p.id) AS comments,
        COALESCE((SELECT STRING_AGG(image_url, ',') FROM post_images WHERE post_id = p.id), '') AS images,
        COALESCE((SELECT STRING_AGG(tag_name, ',') FROM tags WHERE post_id = p.id), '') AS tags,
        COALESCE((SELECT STRING_AGG(video_url, ',') FROM post_videos WHERE post_id = p.id), '') AS videos,
        (SELECT username FROM users WHERE id = p.user_id) AS username
    FROM posts p
    ORDER BY created_at DESC
    OFFSET :offset ROWS
    FETCH NEXT :limit ROWS ONLY
""")

# Get all posts
_get_all_streams = text("""
    SELECT 
        p.id AS post_id,
        p.content,
        p.created_at,
        p.user_id,
        p.has_video,
        COALESCE(u.user_image, '') AS user_image,
        (SELECT COUNT(*) FROM post_likes WHERE post_id = p.id) AS likes,
        (SELECT COUNT(*) FROM saved_posts WHERE post_id = p.id) AS saved,
        (SELECT COUNT(*) FROM comments WHERE post_id = p.id) AS comments,
        COALESCE((
            SELECT STRING_AGG(image_url, ',') 
            FROM post_images 
            WHERE post_id = p.id
        ), '') AS images,
        COALESCE((
            SELECT STRING_AGG(tag_name, ',') 
            FROM tags 
            WHERE post_id = p.id
        ), '') AS tags,
        COALESCE((
            SELECT STRING_AGG(video_url, ',') 
            FROM post_videos 
            WHERE post_id = p.id
        ), '') AS videos,
        u.username
    FROM posts p
    JOIN users u ON u.id = p.user_id
    WHERE p.has_video = 1
    ORDER BY p.created_at DESC
    OFFSET :offset ROWS
    FETCH NEXT :limit ROWS ONLY;
""")

# Get recommended post (sample pattern)
_get_recommeneded_post = text("""
    SELECT 
        p.id AS post_id,
        p.content,
        p.created_at,
        p.user_id,
        p.has_video,        
        COALESCE((SELECT user_image FROM users WHERE id = p.user_id), '') AS user_image,
        (SELECT COUNT(*) FROM post_likes WHERE post_id = p.id) AS likes,
        (SELECT COUNT(*) FROM saved_posts WHERE post_id = p.id) AS saved,
        (SELECT COUNT(*) FROM comments WHERE post_id = p.id) AS comments,
        (SELECT TOP 1 image_url FROM post_images WHERE post_id = p.id) AS images,
        COALESCE((SELECT STRING_AGG(tag_name, ',') FROM tags WHERE post_id = p.id), '') AS tags,
        (SELECT TOP 1 video_url FROM post_videos WHERE post_id = p.id) AS videos,
        (SELECT username FROM users WHERE id = p.user_id) AS username
    FROM posts p
    WHERE p.id != :currentPostId
    ORDER BY NEWID()
    OFFSET 0 ROWS FETCH NEXT :limit ROWS ONLY
""")


# Get single post (sample pattern)
_get_single_post = text("""
    SELECT 
        p.id AS post_id,
        p.content,
        p.created_at,
        p.user_id,
        p.has_video,
        COALESCE((SELECT user_image FROM users WHERE id = p.user_id), '') AS user_image,
        (SELECT COUNT(*) FROM post_likes WHERE post_id = p.id) AS likes,
        (SELECT COUNT(*) FROM saved_posts WHERE post_id = p.id) AS saved,
        (SELECT COUNT(*) FROM comments WHERE post_id = p.id) AS comments,
        (SELECT image_url FROM post_images WHERE post_id = p.id LIMIT 1) AS images,
        COALESCE((SELECT STRING_AGG(tag_name, ',') FROM tags WHERE post_id = p.id), '') AS tags,
        (SELECT video_url FROM post_videos WHERE post_id = p.id LIMIT 1) AS videos,
        (SELECT username FROM users WHERE id = p.user_id) AS username
    FROM posts p
    WHERE p.id = :currentPostId
""")


_get_messaged_group = text("""
    WITH user_conversations AS (
    SELECT cm.conversation_id
    FROM conversation_members cm
    WHERE cm.user_id = :current_user_id
),

other_members AS (
    SELECT cm.conversation_id, u.id AS user_id, u.username, u.user_image
    FROM conversation_members cm
    JOIN users u ON u.id = cm.user_id
    WHERE cm.conversation_id IN (SELECT conversation_id FROM user_conversations)
      AND cm.user_id != :current_user_id
),

last_messages AS (
    SELECT DISTINCT ON (m.conversation_id)
        m.conversation_id,
        m.content AS last_message,
        m.created_at
    FROM messages m
    WHERE m.conversation_id IN (SELECT conversation_id FROM user_conversations)
    ORDER BY m.conversation_id, m.created_at DESC
)

SELECT 
  om.conversation_id,
  c.name AS conversation_name,
  om.user_id, 
  om.username, 
  om.user_image, 
  lm.last_message, 
  lm.created_at
FROM other_members om
JOIN last_messages lm ON lm.conversation_id = om.conversation_id
JOIN conversations c ON c.id = om.conversation_id
ORDER BY lm.created_at DESC;
""")


_get_group_conversations = text("""
    WITH user_conversations AS (
    SELECT cm.conversation_id
    FROM conversation_members cm
    WHERE cm.user_id = :current_user_id
),

group_conversations AS (
    SELECT c.id AS conversation_id, c.name AS group_name, c.created_at
    FROM conversations c
    WHERE c.is_group = 1 AND c.id IN (SELECT conversation_id FROM user_conversations)
),

last_messages AS (
    SELECT DISTINCT ON (m.conversation_id)
        m.conversation_id,
        m.content AS last_message,
        m.created_at
    FROM messages m
    WHERE m.conversation_id IN (SELECT conversation_id FROM group_conversations)
    ORDER BY m.conversation_id, m.created_at DESC
)

SELECT 
    gc.conversation_id, 
    gc.group_name, 
    lm.last_message, 
    lm.created_at
FROM group_conversations gc
LEFT JOIN last_messages lm ON lm.conversation_id = gc.conversation_id
ORDER BY lm.created_at DESC;
""")

_get_messaged_friends = text("""
WITH user_conversations AS (
    SELECT cm.conversation_id
    FROM conversation_members cm
    WHERE cm.user_id = :current_user_id
),

other_members AS (
    SELECT cm.conversation_id, u.id AS user_id, u.username, u.user_image, u.reference_id
    FROM conversation_members cm
    JOIN users u ON u.id = cm.user_id
    WHERE cm.conversation_id IN (SELECT conversation_id FROM user_conversations)
      AND cm.user_id != :current_user_id
),

last_messages AS (
    SELECT DISTINCT ON (m.conversation_id)
        m.conversation_id,
        m.content AS last_message,
        m.created_at
    FROM messages m
    WHERE m.conversation_id IN (SELECT conversation_id FROM user_conversations)
    ORDER BY m.conversation_id, m.created_at DESC
)

SELECT
    om.conversation_id,
    om.user_id,
    om.username,
    om.user_image,
    om.reference_id,
    lm.last_message,
    lm.created_at
FROM other_members om
LEFT JOIN last_messages lm ON lm.conversation_id = om.conversation_id
ORDER BY lm.created_at DESC NULLS LAST;
""")





# "(sqlalchemy.dialects.postgresql.asyncpg.ProgrammingError) <class 'asyncpg.exceptions.UndefinedFunctionError'>: operator does not exist: uuid = character varying
# HINT:  No operator matches the given name and argument types. You might need to add explicit type casts.
# [SQL: 
#     SELECT 
#         n.id,
#         n.user_id,
#         n.actor_id,
#         n.type,
#         n.entity_type,
#         n.entity_id,
#         n.action_id,
#         n.message,
#         COALESCE((SELECT user_image FROM users WHERE id = n.actor_id), '') AS user_image,
#         COALESCE((SELECT username FROM users WHERE id = n.actor_id), '') AS username,
#         COALESCE((SELECT STRING_AGG(image_url, ',') FROM post_images WHERE post_id = n.entity_id ), '') AS images,
#         n.is_read,
#         n.created_at
#     FROM notifications n
#     INNER JOIN users u ON n.user_id = u.id
#     WHERE n.user_id = $1
#     ORDER BY created_at DESC
#     OFFSET $2 ROWS
#     FETCH NEXT $3 ROWS ONLY
# ]
# [parameters: ('02d91a4a-f8ef-48bc-a9bb-bb192a9b2867', 0, 10)]
# (Background on this error at: https://sqlalche.me/e/20/f405)"