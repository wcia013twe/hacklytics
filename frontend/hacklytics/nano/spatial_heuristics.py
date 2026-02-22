"""
Spatial Heuristics Module for Fire Safety Analysis

Implements 3 core spatial heuristics for real-time hazard assessment:
1. Proximity - "The Trigger" - Hazard-to-Victim relationships
2. Obstruction - "The Trap" - Path blocking detection
3. Dominance - "The Severity" - Visual field coverage

Output: Dual format (numerical scores + natural language narratives)
- Scores: Used for edge-based reflex decisions (thresholds, alerts)
- Narratives: Used for RAG system semantic search and LLM reasoning
"""

import math
from typing import List, Dict, Tuple, Optional


# ============================================================================
# VULNERABILITY MAPPING
# ============================================================================

VULNERABILITY_MAP = {
    # Critical - Immediate life threat
    'person': 'CRITICAL',
    'people': 'CRITICAL',
    'firefighter': 'CRITICAL',

    # Explosive - BLEVE risk (Boiling Liquid Expanding Vapor Explosion)
    'gas_tank': 'EXPLOSIVE',
    'gas tank': 'EXPLOSIVE',
    'propane': 'EXPLOSIVE',
    'vehicle': 'EXPLOSIVE',
    'car': 'EXPLOSIVE',
    'truck': 'EXPLOSIVE',

    # Lifeline - Escape routes
    'exit': 'LIFELINE',
    'door': 'LIFELINE',
    'window': 'LIFELINE',

    # Hazards
    'fire': 'HAZARD',
    'smoke': 'HAZARD',
    'debris': 'HAZARD',
    'flame': 'HAZARD',
}


def get_vulnerability_level(label: str) -> str:
    """
    Maps object class labels to vulnerability categories.

    Args:
        label: YOLO class label (e.g., 'person', 'fire')

    Returns:
        Vulnerability category: 'CRITICAL', 'EXPLOSIVE', 'LIFELINE', 'HAZARD', or 'UNKNOWN'
    """
    return VULNERABILITY_MAP.get(label.lower(), 'UNKNOWN')


# ============================================================================
# GEOMETRIC HELPER FUNCTIONS
# ============================================================================

def calculate_centroid(bbox: List[float]) -> Tuple[float, float]:
    """
    Calculate the center point of a bounding box.

    Args:
        bbox: [x1, y1, x2, y2] in pixel coordinates

    Returns:
        (center_x, center_y)
    """
    x1, y1, x2, y2 = bbox
    return ((x1 + x2) / 2, (y1 + y2) / 2)


def calculate_distance(point1: Tuple[float, float], point2: Tuple[float, float]) -> float:
    """
    Euclidean distance between two points.

    Args:
        point1: (x1, y1)
        point2: (x2, y2)

    Returns:
        Distance in pixels
    """
    return math.sqrt((point1[0] - point2[0])**2 + (point1[1] - point2[1])**2)


def calculate_box_area(bbox: List[float]) -> float:
    """
    Calculate bounding box area.

    Args:
        bbox: [x1, y1, x2, y2]

    Returns:
        Area in square pixels
    """
    x1, y1, x2, y2 = bbox
    return (x2 - x1) * (y2 - y1)


def calculate_iou(box1: List[float], box2: List[float]) -> float:
    """
    Intersection over Union (IoU) for two bounding boxes.

    Args:
        box1: [x1, y1, x2, y2]
        box2: [x1, y1, x2, y2]

    Returns:
        IoU score (0.0 to 1.0)
    """
    x1_inter = max(box1[0], box2[0])
    y1_inter = max(box1[1], box2[1])
    x2_inter = min(box1[2], box2[2])
    y2_inter = min(box1[3], box2[3])

    if x2_inter < x1_inter or y2_inter < y1_inter:
        return 0.0

    intersection = (x2_inter - x1_inter) * (y2_inter - y1_inter)
    area1 = calculate_box_area(box1)
    area2 = calculate_box_area(box2)
    union = area1 + area2 - intersection

    return intersection / union if union > 0 else 0.0


def box_overlap(box1: List[float], box2: List[float]) -> bool:
    """
    Check if two bounding boxes overlap at all.

    Args:
        box1: [x1, y1, x2, y2]
        box2: [x1, y1, x2, y2]

    Returns:
        True if boxes overlap, False otherwise
    """
    return not (box1[2] < box2[0] or  # box1 is left of box2
                box1[0] > box2[2] or  # box1 is right of box2
                box1[3] < box2[1] or  # box1 is above box2
                box1[1] > box2[3])    # box1 is below box2


# ============================================================================
# HEURISTIC 1: PROXIMITY (The "Trigger" Logic)
# ============================================================================

def calculate_proximity(
    hazards: List[Dict],
    victims: List[Dict],
    frame_shape: Tuple[int, int]
) -> Tuple[float, str, List[Dict]]:
    """
    Determines if hazards are dangerously close to vulnerable objects.

    Logic:
    - IoU > 0.1: Direct contact (IMMEDIATE THREAT)
    - Distance < 15% of frame diagonal: Dangerous proximity
    - Distance < 30% of frame diagonal: Close proximity

    Args:
        hazards: List of hazard objects (fire, smoke, debris)
        victims: List of vulnerable objects (person, gas_tank, etc.)
        frame_shape: (height, width) of frame

    Returns:
        (proximity_score, narrative, interaction_list)
        - proximity_score: 0.0 (safe) to 1.0 (direct contact)
        - narrative: Human-readable description
        - interaction_list: Detailed proximity relationships
    """
    if not hazards or not victims:
        return 0.0, "No proximity threats detected.", []

    h, w = frame_shape
    frame_diagonal = math.sqrt(h**2 + w**2)

    max_proximity_score = 0.0
    interactions = []
    critical_narratives = []

    for hazard in hazards:
        hazard_center = calculate_centroid(hazard['bbox'])

        for victim in victims:
            victim_center = calculate_centroid(victim['bbox'])

            # Check for direct overlap (IoU)
            iou = calculate_iou(hazard['bbox'], victim['bbox'])
            distance = calculate_distance(hazard_center, victim_center)
            normalized_distance = distance / frame_diagonal

            # Calculate proximity score (inverse of distance)
            if iou > 0.1:
                proximity_score = 1.0  # Direct contact
                threat_level = "IMMEDIATE"
                critical_narratives.append(
                    f"{hazard['label'].capitalize()} in DIRECT CONTACT with {victim['label']}"
                )
            elif normalized_distance < 0.15:
                proximity_score = 0.85
                threat_level = "CRITICAL"
                critical_narratives.append(
                    f"{hazard['label'].capitalize()} dangerously close to {victim['label']}"
                )
            elif normalized_distance < 0.30:
                proximity_score = 0.50
                threat_level = "WARNING"
            else:
                proximity_score = max(0.0, 1.0 - normalized_distance)
                threat_level = "MONITOR"

            max_proximity_score = max(max_proximity_score, proximity_score)

            interactions.append({
                'hazard': hazard['label'],
                'victim': victim['label'],
                'victim_type': victim.get('vulnerability', 'UNKNOWN'),
                'distance_normalized': normalized_distance,
                'iou': iou,
                'proximity_score': proximity_score,
                'threat_level': threat_level
            })

    # Generate narrative
    if critical_narratives:
        narrative = " | ".join(critical_narratives[:2])  # Top 2 threats
    elif max_proximity_score > 0.3:
        narrative = f"Hazards detected near vulnerable objects (proximity: {max_proximity_score:.2f})"
    else:
        narrative = "No immediate proximity threats."

    return max_proximity_score, narrative, interactions


# ============================================================================
# HEURISTIC 2: OBSTRUCTION (The "Trap" Logic)
# ============================================================================

def calculate_obstruction(
    hazards: List[Dict],
    frame_shape: Tuple[int, int]
) -> Tuple[bool, float, str, Dict]:
    """
    Determines if hazards are blocking the forward path using First-Person
    Perspective (FPV) center-lane heuristic.

    Logic:
    - Center corridor: 30-70% of frame width (40% center lane)
    - Blocked if hazard occupies >30% of corridor width
    - Bottom 30% checked for exit clearance

    Args:
        hazards: List of hazard objects
        frame_shape: (height, width)

    Returns:
        (is_blocked, obstruction_score, narrative, details)
        - is_blocked: Boolean flag
        - obstruction_score: 0.0 (clear) to 1.0 (fully blocked)
        - narrative: Path status description
        - details: Dict with corridor info
    """
    if not hazards:
        return False, 0.0, "Path ahead is clear.", {'corridor_clear': True}

    h, w = frame_shape

    # Define center corridor (30-70% of width)
    path_min_x = w * 0.30
    path_max_x = w * 0.70
    corridor_width = path_max_x - path_min_x

    # Define bottom zone (potential exit area)
    bottom_zone_y = h * 0.70

    max_obstruction = 0.0
    blocking_hazards = []
    exit_blocked = False

    for hazard in hazards:
        x1, y1, x2, y2 = hazard['bbox']

        # Check overlap with center corridor
        overlap_x1 = max(x1, path_min_x)
        overlap_x2 = min(x2, path_max_x)

        if overlap_x2 > overlap_x1:
            # Calculate what percentage of corridor is blocked
            overlap_width = overlap_x2 - overlap_x1
            corridor_coverage = overlap_width / corridor_width

            # Calculate vertical presence (height coverage)
            box_height = y2 - y1
            vertical_coverage = box_height / h

            # Obstruction score combines width and height
            obstruction_score = corridor_coverage * (0.7 + 0.3 * vertical_coverage)

            max_obstruction = max(max_obstruction, obstruction_score)

            if corridor_coverage > 0.30:  # >30% of corridor blocked
                blocking_hazards.append({
                    'label': hazard['label'],
                    'coverage': corridor_coverage,
                    'score': obstruction_score
                })

            # Check if blocking bottom exit zone
            if y2 > bottom_zone_y and corridor_coverage > 0.40:
                exit_blocked = True

    is_blocked = max_obstruction > 0.30

    # Generate narrative
    if is_blocked:
        blocker_labels = [h['label'] for h in blocking_hazards]
        blocker_str = ', '.join(set(blocker_labels))
        narrative = f"Path OBSTRUCTED by {blocker_str}. "

        if exit_blocked:
            narrative += "Exit zone blocked."
        else:
            # Check for clearance on sides
            # This is a simplified version - could be enhanced
            narrative += "Seek alternative route."
    else:
        narrative = "Path ahead is clear."

    details = {
        'corridor_clear': not is_blocked,
        'max_obstruction': max_obstruction,
        'blocking_hazards': blocking_hazards,
        'exit_blocked': exit_blocked
    }

    return is_blocked, max_obstruction, narrative, details


# ============================================================================
# HEURISTIC 3: DOMINANCE (The "Severity" Logic)
# ============================================================================

def calculate_dominance(
    hazard_boxes: List[Dict],
    frame_shape: Tuple[int, int]
) -> Tuple[float, str, str]:
    """
    Calculates how much of the visual field is consumed by hazards.

    Severity Levels:
    - < 10%: Spot fire (extinguishable)
    - 10-30%: Moderate fire
    - 30-60%: Major fire
    - > 60%: Flashover imminent (evacuate)

    Args:
        hazard_boxes: List of hazard objects
        frame_shape: (height, width)

    Returns:
        (coverage_percentage, severity_level, narrative)
    """
    if not hazard_boxes:
        return 0.0, "SAFE", "No visible hazards."

    h, w = frame_shape
    frame_area = h * w

    # Calculate total hazard area (with overlap handling)
    # Simple approach: sum all boxes (may double-count overlaps)
    # For production: use polygon union for exact coverage
    total_hazard_area = sum(calculate_box_area(haz['bbox']) for haz in hazard_boxes)

    coverage_percentage = (total_hazard_area / frame_area) * 100

    # Determine severity level
    if coverage_percentage < 10:
        severity_level = "MINOR"
        narrative = f"Small fire detected ({coverage_percentage:.1f}% coverage). Extinguishable."
    elif coverage_percentage < 30:
        severity_level = "MODERATE"
        narrative = f"Moderate fire ({coverage_percentage:.1f}% coverage). Proceed with caution."
    elif coverage_percentage < 60:
        severity_level = "MAJOR"
        narrative = f"Major fire engulfs {coverage_percentage:.1f}% of visual field. High risk."
    else:
        severity_level = "CRITICAL"
        narrative = f"CRITICAL: Fire dominates {coverage_percentage:.1f}% of view. FLASHOVER RISK. EVACUATE."

    return coverage_percentage, severity_level, narrative


# ============================================================================
# UNIFIED SCENE ANALYSIS
# ============================================================================

def compute_scene_heuristics(
    all_detections: List[Dict],
    frame_shape: Tuple[int, int]
) -> Dict:
    """
    Computes all spatial heuristics and generates unified output.

    Args:
        all_detections: List of detection dicts with keys:
            - 'label': class name
            - 'bbox': [x1, y1, x2, y2]
            - 'confidence': detection score
        frame_shape: (height, width)

    Returns:
        Dictionary with:
            - scores: Numerical metrics
            - narrative: Combined natural language description
            - details: Detailed analysis results
    """
    # Classify detections by type
    hazards = []
    victims = []

    for det in all_detections:
        vulnerability = get_vulnerability_level(det['label'])
        det['vulnerability'] = vulnerability

        if vulnerability == 'HAZARD':
            hazards.append(det)
        elif vulnerability in ['CRITICAL', 'EXPLOSIVE', 'LIFELINE']:
            victims.append(det)
        else:
            # Unknown objects - treat as potential victims for safety
            victims.append(det)

    # Compute each heuristic
    proximity_score, proximity_narrative, proximity_details = calculate_proximity(
        hazards, victims, frame_shape
    )

    is_obstructed, obstruction_score, obstruction_narrative, obstruction_details = calculate_obstruction(
        hazards, frame_shape
    )

    # Only compute dominance for actual fire/smoke hazards
    fire_hazards = [h for h in hazards if h['label'].lower() in ['fire', 'flame', 'smoke']]
    dominance_coverage, dominance_level, dominance_narrative = calculate_dominance(
        fire_hazards, frame_shape
    )

    # Generate unified narrative
    narrative_parts = []

    if dominance_level in ['MAJOR', 'CRITICAL']:
        narrative_parts.append(dominance_narrative)

    if is_obstructed:
        narrative_parts.append(obstruction_narrative)

    if proximity_score > 0.5:
        narrative_parts.append(proximity_narrative)

    unified_narrative = " ".join(narrative_parts) if narrative_parts else "Scene is safe."

    return {
        'scores': {
            'proximity': round(proximity_score, 3),
            'obstruction': round(obstruction_score, 3),
            'dominance': round(dominance_coverage / 100, 3),  # Normalize to 0-1
        },
        'narrative': unified_narrative,
        'details': {
            'proximity': proximity_details,
            'obstruction': obstruction_details,
            'dominance': {
                'coverage_pct': round(dominance_coverage, 2),
                'severity_level': dominance_level,
                'hazard_count': len(fire_hazards)
            }
        }
    }


# ============================================================================
# FUTURE HEURISTICS (Placeholder - Commented for Phase 2)
# ============================================================================

"""
# HEURISTIC 4: ELEVATION (The "Smoke Layer" Logic)
def calculate_elevation(smoke_boxes: List[Dict], frame_shape: Tuple[int, int]) -> Tuple[float, str]:
    '''
    Determines if smoke is banking down (thermal layering indicator).

    Logic:
    - Check if smoke bounding boxes extend below 50% of frame height
    - Lower smoke = more dangerous (indicates hot gas layer descending)

    Returns:
        (smoke_layer_height, narrative)
    '''
    # Implementation for Phase 2
    pass


# HEURISTIC 5: ORIENTATION (The "Guide" Logic)
def calculate_orientation(clear_zones: List[Dict], frame_shape: Tuple[int, int]) -> str:
    '''
    Provides directional guidance based on clear space detection.

    Logic:
    - Divide frame into left (0-33%), center (33-66%), right (66-100%)
    - Identify which zones are free of hazards

    Returns:
        narrative: "Clear path on the right" / "Move left" / "No clear direction"
    '''
    # Implementation for Phase 2
    pass
"""
