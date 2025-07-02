def recommend_posts(user_interests, posts, db):
    user_interest_arr = [row[0] for row in user_interests]
    
    
        
    columns = [
        "post_id", "content", "created_at", "user_id",
        "user_image","likes", "saved", "comments", "images", "tags", "videos", "username"
    ]

    posts_arr = [
        dict(zip(columns, row))
        for row in posts 
    ]
       
    recommendations = []
    
    for post in posts_arr:
        # Step 1: Check tag match
        
        tags_string = getattr(post, "tags", "") or ""
        
        # split the tags if string is available
        post_tags = tags_string.split(",") if tags_string else []
        
        tag_match = len(set(user_interest_arr) & set(post_tags))
        print(f"Tag match: {tag_match}")

        # Step 2: Calculate engagement score
        engagement_score = (post["likes"] * 1) + (post["comments"] * 2) + (post["saved"] * 3)
        
        # Step 3: Overall score
        if not tag_match and not engagement_score:
            continue
        
        total_score = (tag_match * 10) + engagement_score
        
        recommendations.append({
            "post_id": post["post_id"],
            "score": total_score
        })
    
    # Step 4: Sort by highest score
    recommendations = sorted(recommendations, key=lambda x: x["score"], reverse=True)
    
    return recommendations
