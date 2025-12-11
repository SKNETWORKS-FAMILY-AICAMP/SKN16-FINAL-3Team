-- 매칭 문제 해결 SQL 스크립트
-- 권도형 멘토와 홍예미, 황나미 멘티의 매칭 정리

-- 1. 현재 상태 확인
SELECT 
    r.id,
    u1.name as mentor_name,
    u2.name as mentee_name,
    r.is_active,
    r.matched_at
FROM mentor_mentee_relations r
JOIN users u1 ON r.mentor_id = u1.id
JOIN users u2 ON r.mentee_id = u2.id
WHERE u1.name = '권도형' 
  AND u2.name IN ('홍예미', '황나미')
ORDER BY u2.name, r.matched_at DESC;

-- 2. 각 멘티별로 가장 최근 매칭만 활성화하고 나머지 비활성화
-- 홍예미 처리
WITH latest_relation AS (
    SELECT r.id
    FROM mentor_mentee_relations r
    JOIN users u1 ON r.mentor_id = u1.id
    JOIN users u2 ON r.mentee_id = u2.id
    WHERE u1.name = '권도형' 
      AND u2.name = '홍예미'
    ORDER BY r.matched_at DESC
    LIMIT 1
)
UPDATE mentor_mentee_relations
SET is_active = (id IN (SELECT id FROM latest_relation))
WHERE id IN (
    SELECT r.id
    FROM mentor_mentee_relations r
    JOIN users u1 ON r.mentor_id = u1.id
    JOIN users u2 ON r.mentee_id = u2.id
    WHERE u1.name = '권도형' 
      AND u2.name = '홍예미'
);

-- 황나미 처리
WITH latest_relation AS (
    SELECT r.id
    FROM mentor_mentee_relations r
    JOIN users u1 ON r.mentor_id = u1.id
    JOIN users u2 ON r.mentee_id = u2.id
    WHERE u1.name = '권도형' 
      AND u2.name = '황나미'
    ORDER BY r.matched_at DESC
    LIMIT 1
)
UPDATE mentor_mentee_relations
SET is_active = (id IN (SELECT id FROM latest_relation))
WHERE id IN (
    SELECT r.id
    FROM mentor_mentee_relations r
    JOIN users u1 ON r.mentor_id = u1.id
    JOIN users u2 ON r.mentee_id = u2.id
    WHERE u1.name = '권도형' 
      AND u2.name = '황나미'
);

-- 3. 최종 확인
SELECT 
    u1.name as mentor_name,
    u2.name as mentee_name,
    r.is_active,
    COUNT(*) as count
FROM mentor_mentee_relations r
JOIN users u1 ON r.mentor_id = u1.id
JOIN users u2 ON r.mentee_id = u2.id
WHERE u1.name = '권도형' 
  AND u2.name IN ('홍예미', '황나미')
GROUP BY u1.name, u2.name, r.is_active
ORDER BY u2.name, r.is_active DESC;



