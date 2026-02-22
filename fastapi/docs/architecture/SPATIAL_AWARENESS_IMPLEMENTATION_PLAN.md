# Spatial Awareness Implementation Plan
**iPhone IMU + ARKit + LiDAR Integration**

**Author:** Claude Code · **Date:** 2026-02-21 · **Version:** 1.0 · **Status:** Implementation Ready

---

## Executive Summary

This document defines the end-to-end implementation plan for adding spatial awareness to the fire safety system, enabling:

1. **Camera motion detection** - Distinguish fire growth from camera movement
2. **Depth-aware severity** - Adjust hazard levels based on distance to fire
3. **Spatial fire progression** - Track fire spread across rooms/locations
4. **Trajectory analysis** - Understand victim movement patterns

**Architecture Impact:** Data flows from iPhone sensors → Edge Processing → Backend Pipeline → RAG Context → Dashboard Visualization

**Timeline:** 2-3 weeks for Tier 1 (IMU + Pose + Sparse Depth)

---

## 1. System Architecture Changes

### 1.1 Data Flow Overview

```
┌─────────────────────────────────────────────────────────────────┐
│ iPhone Edge Device (NEW: CoreMotion + ARKit + LiDAR)           │
├─────────────────────────────────────────────────────────────────┤
│ 1. CoreMotion: IMU (gyro, accel) @ 60Hz                        │
│ 2. ARKit: 6-DOF camera pose @ 30Hz                             │
│ 3. LiDAR: Depth values for detected objects                    │
│ 4. Spatial Processor: Motion state, depth normalization        │
└──────────────┬──────────────────────────────────────────────────┘
               │ Enhanced Telemetry Packet (+100 bytes)
               │ spatial: {pose, depths, motion_state, room_id}
               ▼
┌─────────────────────────────────────────────────────────────────┐
│ Backend: Ingest Service (UPDATED)                              │
├─────────────────────────────────────────────────────────────────┤
│ 1. Validate spatial context                                    │
│ 2. Buffer spatial history (pose trajectory)                    │
│ 3. Compute spatial trends (camera motion, fire spread)         │
└──────────────┬──────────────────────────────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────────────────────────────┐
│ Backend: Temporal Buffer (UPDATED)                             │
├─────────────────────────────────────────────────────────────────┤
│ 1. Motion-corrected fire growth rates                          │
│ 2. Depth-adjusted severity scores                              │
│ 3. Spatial trajectory analysis                                 │
└──────────────┬──────────────────────────────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────────────────────────────┐
│ Backend: RAG Service (UPDATED)                                 │
├─────────────────────────────────────────────────────────────────┤
│ 1. Enhanced narrative with spatial progression                 │
│ 2. Spatial-aware protocol retrieval                            │
│ 3. Room-level incident logging                                 │
└──────────────┬──────────────────────────────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────────────────────────────┐
│ Frontend: Dashboard (UPDATED)                                  │
├─────────────────────────────────────────────────────────────────┤
│ 1. 2D spatial map view (camera path, fire locations)           │
│ 2. Depth-aware severity indicators                             │
│ 3. Trajectory visualization (victim movement)                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 2. Data Model Changes

### 2.1 New Pydantic Models (contracts/models.py)

```python
# FILE: fastapi/backend/contracts/models.py

from pydantic import BaseModel, Field, validator
from typing import Tuple, Optional, Literal, Dict

class CameraPose(BaseModel):
    """
    6-DOF camera pose from ARKit.

    Coordinate System: ARKit world coordinates (meters)
    - X: Right (positive = right of origin)
    - Y: Up (positive = up from ground)
    - Z: Forward (positive = away from camera start position)

    Orientation: Quaternion (w, x, y, z)
    - Normalized to unit length
    - ARKit provides camera-to-world transform
    """
    position: Tuple[float, float, float] = Field(
        ...,
        description="(x, y, z) in meters, ARKit world coordinates"
    )
    orientation: Tuple[float, float, float, float] = Field(
        ...,
        description="Quaternion (w, x, y, z) for camera orientation"
    )
    velocity: Optional[Tuple[float, float, float]] = Field(
        None,
        description="Camera linear velocity (vx, vy, vz) in m/s. Used for motion detection."
    )
    tracking_state: Literal["NORMAL", "LIMITED", "NOT_AVAILABLE"] = Field(
        default="NORMAL",
        description="ARKit tracking quality. LIMITED = poor lighting/features, NOT_AVAILABLE = tracking lost"
    )

    @validator('orientation')
    def validate_quaternion(cls, v):
        """Ensure quaternion is normalized to unit length."""
        w, x, y, z = v
        magnitude = (w**2 + x**2 + y**2 + z**2) ** 0.5
        if not (0.99 <= magnitude <= 1.01):  # Allow 1% tolerance for float precision
            raise ValueError(f"Quaternion must be normalized. Got magnitude {magnitude:.4f}")
        return v


class ObjectDepth(BaseModel):
    """
    LiDAR depth measurement for a specific tracked object.

    Depth is measured from camera to object centroid using LiDAR point cloud.
    Confidence indicates measurement quality (0.0 = unreliable, 1.0 = high confidence).
    """
    object_id: int = Field(..., description="Tracked object ID (from BoT-SORT)")
    object_label: str = Field(..., description="YOLO class label (fire, person, etc.)")
    depth_meters: float = Field(
        ...,
        ge=0.1,
        le=50.0,
        description="Distance from camera to object in meters. Range: 0.1m - 50m (LiDAR limits)"
    )
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Depth measurement confidence (0.0 = unreliable, 1.0 = high confidence)"
    )


class SpatialContext(BaseModel):
    """
    Spatial awareness data from iPhone sensors (IMU + ARKit + LiDAR).

    This context enables:
    - Camera motion compensation (distinguish fire growth from camera zoom)
    - Depth-aware severity (fire 2m away vs 20m away)
    - Spatial fire progression (fire spreading from room A to room B)
    - Trajectory analysis (victim moving toward exit)
    """
    camera_pose: CameraPose = Field(..., description="6-DOF camera pose from ARKit")

    object_depths: Dict[str, ObjectDepth] = Field(
        default_factory=dict,
        description="LiDAR depth for each tracked object. Key format: '{label}_{id}' (e.g., 'fire_7', 'person_42')"
    )

    camera_motion_state: Literal["STATIC", "PANNING", "WALKING", "RUNNING"] = Field(
        default="STATIC",
        description="Classified camera motion state based on velocity and rotation rate"
    )

    room_id: Optional[str] = Field(
        None,
        description="ARKit spatial anchor ID for current room/location. Format: 'room_{uuid}'. Enables room-level fire tracking."
    )

    floor_plane_detected: bool = Field(
        default=False,
        description="Has ARKit detected a floor plane? Required for accurate Y-axis positioning."
    )


class TelemetryPacket(BaseModel):
    """
    UPDATED: Add spatial_context field to existing telemetry packet.

    Backward Compatibility:
    - spatial_context is Optional (defaults to None)
    - Existing Jetson Nano packets (without spatial data) continue to work
    - New iPhone packets include full spatial context
    """
    device_id: str = Field(..., pattern=r"(jetson|iphone)_\w+")  # UPDATED: Allow "iphone_" prefix
    session_id: str = Field(..., pattern=r"mission_\w+")
    timestamp: float
    hazard_level: Literal["CLEAR", "LOW", "MODERATE", "HIGH", "CRITICAL"]
    scores: Scores
    tracked_objects: List[TrackedObject]
    visual_narrative: str = Field(..., max_length=200, min_length=1)
    priority: Optional[Literal["CRITICAL", "CAUTION", "SAFE"]] = None

    # NEW: Spatial awareness (optional for backward compatibility)
    spatial_context: Optional[SpatialContext] = Field(
        None,
        description="Spatial awareness data from iPhone sensors. None for legacy Jetson devices."
    )
```

**Backward Compatibility:** Existing Jetson packets without `spatial_context` continue to work. Only iPhone devices send spatial data.

---

### 2.2 Enhanced Trend Result (Spatial Trends)

```python
# FILE: fastapi/backend/contracts/models.py

class SpatialTrendResult(BaseModel):
    """
    Spatial trend analysis result from enhanced TemporalBuffer.

    Extends basic fire growth trends with spatial awareness:
    - Camera motion compensation
    - Depth-adjusted severity
    - Spatial fire spread vectors
    - Victim trajectory analysis
    """
    # EXISTING: Fire severity trend (keep unchanged)
    severity_trend: Literal["RAPID_GROWTH", "GROWING", "STABLE", "DIMINISHING", "UNKNOWN"]
    severity_growth_rate: float = Field(..., description="Change in fire_dominance per second")

    # NEW: Camera motion analysis
    camera_motion_detected: bool = Field(
        default=False,
        description="True if significant camera movement detected in buffer window"
    )
    camera_displacement_meters: Optional[float] = Field(
        None,
        description="Total camera displacement in meters over buffer window"
    )
    motion_corrected_growth_rate: Optional[float] = Field(
        None,
        description="Fire growth rate after compensating for camera motion. None if no spatial data."
    )

    # NEW: Depth-adjusted severity
    average_fire_depth_meters: Optional[float] = Field(
        None,
        description="Average distance to fire over buffer window. None if no depth data."
    )
    depth_adjusted_severity: Optional[float] = Field(
        None,
        ge=0.0,
        le=1.0,
        description="Severity score adjusted for distance (close fire = higher severity)"
    )

    # NEW: Spatial fire spread
    fire_spread_vector: Optional[Tuple[float, float, float]] = Field(
        None,
        description="3D vector (x, y, z) showing direction of fire movement in meters. None if <2 samples."
    )
    fire_spread_rate_meters_per_sec: Optional[float] = Field(
        None,
        description="Speed of fire spread in m/s. None if no spatial progression detected."
    )
    room_transitions: List[Tuple[str, str, float]] = Field(
        default_factory=list,
        description="List of (from_room, to_room, timestamp) transitions detected in buffer"
    )

    # NEW: Victim trajectory
    victim_trajectories: Dict[int, Dict] = Field(
        default_factory=dict,
        description="""
        Per-victim movement analysis. Key = object_id, Value = {
            'start_position': (x, y, z),
            'end_position': (x, y, z),
            'velocity': (vx, vy, vz),
            'moving_toward_exit': bool,
            'moving_toward_hazard': bool
        }
        """
    )

    # Metadata
    sample_count: int
    time_span: float
    spatial_data_available: bool = Field(
        default=False,
        description="True if buffer contains spatial context data"
    )
```

---

## 3. iPhone Edge Device Implementation

### 3.1 New Swift Module: SpatialSensorManager

```swift
// FILE: ios/FireSafety/SpatialSensorManager.swift

import Foundation
import ARKit
import CoreMotion

/// Manages iPhone spatial sensors (IMU, ARKit, LiDAR)
class SpatialSensorManager: NSObject, ObservableObject {

    // MARK: - Sensor Instances
    private let arSession: ARSession
    private let motionManager: CMMotionManager
    private var currentFrame: ARFrame?

    // MARK: - State
    @Published var trackingState: ARCamera.TrackingState = .notAvailable
    @Published var cameraPose: CameraPose?
    @Published var cameraMotionState: CameraMotionState = .static

    // MARK: - Configuration
    private let depthSamplingRadius: Float = 0.2  // meters around object centroid
    private let motionDetectionThreshold: Float = 0.3  // m/s velocity threshold

    override init() {
        self.arSession = ARSession()
        self.motionManager = CMMotionManager()
        super.init()

        configureARSession()
        configureMotionManager()
    }

    // MARK: - ARKit Configuration
    private func configureARSession() {
        let config = ARWorldTrackingConfiguration()

        // Enable LiDAR depth (iPhone 12 Pro and later)
        if ARWorldTrackingConfiguration.supportsSceneReconstruction(.mesh) {
            config.sceneReconstruction = .mesh
        }

        // Enable plane detection for floor reference
        config.planeDetection = [.horizontal]

        // Enable frame semantics for depth
        if ARWorldTrackingConfiguration.supportsFrameSemantics(.sceneDepth) {
            config.frameSemantics = .sceneDepth
        }

        arSession.delegate = self
        arSession.run(config)
    }

    private func configureMotionManager() {
        motionManager.deviceMotionUpdateInterval = 1.0 / 60.0  // 60Hz
        motionManager.startDeviceMotionUpdates()
    }

    // MARK: - Public Interface

    /// Get current camera pose from ARKit
    func getCurrentPose() -> CameraPose? {
        guard let frame = currentFrame else { return nil }

        let camera = frame.camera
        let transform = camera.transform

        // Extract position (translation from transform matrix)
        let position = SIMD3<Float>(
            transform.columns.3.x,
            transform.columns.3.y,
            transform.columns.3.z
        )

        // Extract orientation (quaternion from rotation matrix)
        let orientation = simd_quatf(transform)

        // Calculate velocity from motion manager
        var velocity: SIMD3<Float>? = nil
        if let deviceMotion = motionManager.deviceMotion {
            let userAccel = deviceMotion.userAcceleration
            velocity = SIMD3<Float>(
                Float(userAccel.x),
                Float(userAccel.y),
                Float(userAccel.z)
            )
        }

        return CameraPose(
            position: (position.x, position.y, position.z),
            orientation: (orientation.real, orientation.imag.x, orientation.imag.y, orientation.imag.z),
            velocity: velocity != nil ? (velocity!.x, velocity!.y, velocity!.z) : nil,
            trackingState: mapTrackingState(camera.trackingState)
        )
    }

    /// Get LiDAR depth for a specific bounding box
    func getDepthForObject(bbox: CGRect, label: String, objectId: Int) -> ObjectDepth? {
        guard let frame = currentFrame,
              let depthMap = frame.sceneDepth?.depthMap else {
            return nil
        }

        // Convert bbox center to normalized image coordinates
        let centerX = bbox.midX
        let centerY = bbox.midY

        // Sample depth values in a small radius around object centroid
        let depths = sampleDepthMap(
            depthMap: depthMap,
            centerX: centerX,
            centerY: centerY,
            samplingRadius: 10  // pixels
        )

        guard !depths.isEmpty else { return nil }

        // Use median depth (robust to outliers)
        let medianDepth = depths.sorted()[depths.count / 2]

        // Calculate confidence based on depth variance
        let variance = calculateVariance(depths)
        let confidence = max(0.0, min(1.0, 1.0 - variance / 0.5))

        return ObjectDepth(
            objectId: objectId,
            objectLabel: label,
            depthMeters: medianDepth,
            confidence: confidence
        )
    }

    /// Classify camera motion state based on velocity and rotation
    func classifyCameraMotion() -> CameraMotionState {
        guard let deviceMotion = motionManager.deviceMotion else {
            return .static
        }

        let userAccel = deviceMotion.userAcceleration
        let velocity = sqrt(
            userAccel.x * userAccel.x +
            userAccel.y * userAccel.y +
            userAccel.z * userAccel.z
        )

        let rotationRate = deviceMotion.rotationRate
        let angularVelocity = sqrt(
            rotationRate.x * rotationRate.x +
            rotationRate.y * rotationRate.y +
            rotationRate.z * rotationRate.z
        )

        // Classification thresholds
        if velocity > 2.0 {
            return .running
        } else if velocity > 0.5 {
            return .walking
        } else if angularVelocity > 0.5 {
            return .panning
        } else {
            return .static
        }
    }

    // MARK: - Helper Methods

    private func sampleDepthMap(
        depthMap: CVPixelBuffer,
        centerX: CGFloat,
        centerY: CGFloat,
        samplingRadius: Int
    ) -> [Float] {
        CVPixelBufferLockBaseAddress(depthMap, .readOnly)
        defer { CVPixelBufferUnlockBaseAddress(depthMap, .readOnly) }

        let width = CVPixelBufferGetWidth(depthMap)
        let height = CVPixelBufferGetHeight(depthMap)
        let baseAddress = CVPixelBufferGetBaseAddress(depthMap)
        let bytesPerRow = CVPixelBufferGetBytesPerRow(depthMap)

        var depths: [Float] = []

        let pixelX = Int(centerX * CGFloat(width))
        let pixelY = Int(centerY * CGFloat(height))

        for dy in -samplingRadius...samplingRadius {
            for dx in -samplingRadius...samplingRadius {
                let x = pixelX + dx
                let y = pixelY + dy

                guard x >= 0, x < width, y >= 0, y < height else { continue }

                let offset = y * bytesPerRow + x * MemoryLayout<Float32>.size
                let depthValue = baseAddress!.load(fromByteOffset: offset, as: Float32.self)

                if depthValue > 0 && depthValue < 50.0 {  // Valid LiDAR range
                    depths.append(depthValue)
                }
            }
        }

        return depths
    }

    private func calculateVariance(_ values: [Float]) -> Float {
        guard !values.isEmpty else { return 0.0 }

        let mean = values.reduce(0, +) / Float(values.count)
        let variance = values.map { pow($0 - mean, 2) }.reduce(0, +) / Float(values.count)
        return variance
    }

    private func mapTrackingState(_ state: ARCamera.TrackingState) -> String {
        switch state {
        case .normal:
            return "NORMAL"
        case .limited:
            return "LIMITED"
        case .notAvailable:
            return "NOT_AVAILABLE"
        }
    }
}

// MARK: - ARSessionDelegate

extension SpatialSensorManager: ARSessionDelegate {
    func session(_ session: ARSession, didUpdate frame: ARFrame) {
        self.currentFrame = frame
        self.trackingState = frame.camera.trackingState
        self.cameraPose = getCurrentPose()
        self.cameraMotionState = classifyCameraMotion()
    }
}

// MARK: - Supporting Types

enum CameraMotionState: String, Codable {
    case `static` = "STATIC"
    case panning = "PANNING"
    case walking = "WALKING"
    case running = "RUNNING"
}

struct CameraPose: Codable {
    let position: (Float, Float, Float)
    let orientation: (Float, Float, Float, Float)
    let velocity: (Float, Float, Float)?
    let trackingState: String
}

struct ObjectDepth: Codable {
    let objectId: Int
    let objectLabel: String
    let depthMeters: Float
    let confidence: Float
}
```

---

### 3.2 Integration into Reflex Engine (iPhone Version)

```swift
// FILE: ios/FireSafety/ReflexEngine.swift

import Foundation

class ReflexEngine {
    private let spatialManager: SpatialSensorManager
    private let backendURL: URL

    init(backendURL: String) {
        self.backendURL = URL(string: backendURL)!
        self.spatialManager = SpatialSensorManager()
    }

    func processFrame(
        yoloResults: [YOLODetection],
        thermalMax: Float,
        smokeDetected: Bool
    ) {
        // 1. Run existing spatial heuristics (proximity, obstruction, dominance)
        let heuristics = computeSceneHeuristics(yoloResults)

        // 2. NEW: Gather spatial context
        let spatialContext = buildSpatialContext(yoloResults)

        // 3. Build telemetry packet (UPDATED with spatial context)
        let packet = TelemetryPacket(
            deviceId: "iphone_alpha_01",
            sessionId: getCurrentSessionId(),
            timestamp: Date().timeIntervalSince1970,
            hazardLevel: determineHazardLevel(heuristics, thermalMax),
            scores: Scores(
                fireDominance: heuristics.dominance,
                smokeOpacity: smokeDetected ? 0.8 : 0.0,
                proximityAlert: heuristics.proximityScore > 0.7
            ),
            trackedObjects: mapTrackedObjects(yoloResults),
            visualNarrative: generateNarrative(heuristics),
            priority: nil,
            spatialContext: spatialContext  // NEW
        )

        // 4. Transmit to backend
        transmitPacket(packet)
    }

    // NEW: Build spatial context from sensors
    private func buildSpatialContext(_ detections: [YOLODetection]) -> SpatialContext? {
        guard let cameraPose = spatialManager.getCurrentPose() else {
            return nil  // ARKit tracking not available
        }

        // Get depth for each detected object
        var objectDepths: [String: ObjectDepth] = [:]
        for detection in detections {
            if let depth = spatialManager.getDepthForObject(
                bbox: detection.bbox,
                label: detection.label,
                objectId: detection.id
            ) {
                let key = "\(detection.label)_\(detection.id)"
                objectDepths[key] = depth
            }
        }

        return SpatialContext(
            cameraPose: cameraPose,
            objectDepths: objectDepths,
            cameraMotionState: spatialManager.cameraMotionState.rawValue,
            roomId: nil,  // TODO: ARKit room detection (Phase 2)
            floorPlaneDetected: spatialManager.hasFloorPlane
        )
    }
}
```

---

## 4. Backend Pipeline Updates

### 4.1 Ingest Service: Spatial Validation

```python
# FILE: fastapi/backend/main_ingest.py

from contracts.models import TelemetryPacket, SpatialContext
import logging

logger = logging.getLogger(__name__)

async def validate_spatial_context(spatial: SpatialContext) -> bool:
    """
    Validate spatial context data quality.

    Checks:
    - ARKit tracking state is NORMAL (not LIMITED or NOT_AVAILABLE)
    - Quaternion is normalized
    - Depth values are in valid range (0.1m - 50m)
    - No NaN or Inf values
    """
    # Check tracking state
    if spatial.camera_pose.tracking_state != "NORMAL":
        logger.warning(f"ARKit tracking state: {spatial.camera_pose.tracking_state}")
        return False

    # Validate quaternion normalization
    w, x, y, z = spatial.camera_pose.orientation
    magnitude = (w**2 + x**2 + y**2 + z**2) ** 0.5
    if not (0.99 <= magnitude <= 1.01):
        logger.error(f"Invalid quaternion magnitude: {magnitude}")
        return False

    # Validate depth values
    for key, depth_obj in spatial.object_depths.items():
        if not (0.1 <= depth_obj.depth_meters <= 50.0):
            logger.warning(f"Invalid depth for {key}: {depth_obj.depth_meters}m")
            return False

        if depth_obj.confidence < 0.3:
            logger.warning(f"Low confidence depth for {key}: {depth_obj.confidence}")

    return True


@app.post("/ingest")
async def ingest_telemetry(packet: TelemetryPacket):
    """
    UPDATED: Validate spatial context if present.
    """
    # NEW: Validate spatial data
    if packet.spatial_context:
        if not await validate_spatial_context(packet.spatial_context):
            logger.warning("Spatial context validation failed, continuing without spatial data")
            packet.spatial_context = None  # Degrade gracefully

    # Existing ingestion logic continues...
    result = await orchestrator.process_packet(packet)
    return result
```

---

### 4.2 Temporal Buffer: Spatial Trend Analysis

```python
# FILE: fastapi/backend/agents/spatial_temporal_buffer.py

"""
Enhanced Temporal Buffer with Spatial Awareness.

Extends TemporalBufferAgent with:
- Camera motion compensation
- Depth-adjusted severity
- Spatial fire spread tracking
- Victim trajectory analysis
"""

import numpy as np
from typing import Dict, List, Tuple, Optional
from collections import deque
from contracts.models import TelemetryPacket, SpatialTrendResult, CameraPose
import logging

logger = logging.getLogger(__name__)


class SpatialTemporalBuffer:
    """
    Temporal buffer with spatial awareness.

    Maintains:
    - Packet buffer (existing)
    - Camera pose trajectory
    - Object depth history
    - Room transition log
    """

    def __init__(self, window_seconds: float = 10.0):
        self.window_seconds = window_seconds
        self.packet_buffer: deque = deque()
        self.pose_trajectory: deque = deque()  # NEW: Camera pose history
        self.depth_history: Dict[str, deque] = {}  # NEW: Per-object depth timeline
        self.room_transitions: List[Tuple[str, str, float]] = []  # NEW: Room changes

    async def insert_packet(self, packet: TelemetryPacket):
        """
        UPDATED: Buffer spatial context alongside packet.
        """
        # Existing packet buffering
        self.packet_buffer.append(packet)

        # NEW: Buffer spatial data
        if packet.spatial_context:
            self.pose_trajectory.append({
                'timestamp': packet.timestamp,
                'pose': packet.spatial_context.camera_pose,
                'motion_state': packet.spatial_context.camera_motion_state
            })

            # Track object depths over time
            for key, depth_obj in packet.spatial_context.object_depths.items():
                if key not in self.depth_history:
                    self.depth_history[key] = deque()

                self.depth_history[key].append({
                    'timestamp': packet.timestamp,
                    'depth': depth_obj.depth_meters,
                    'confidence': depth_obj.confidence
                })

            # Detect room transitions
            if packet.spatial_context.room_id:
                await self._track_room_transition(
                    packet.spatial_context.room_id,
                    packet.timestamp
                )

        # Evict stale data
        await self._evict_stale()

    async def compute_spatial_trend(self) -> SpatialTrendResult:
        """
        NEW: Compute spatial-aware trends.

        Returns motion-corrected fire growth, depth-adjusted severity,
        fire spread vectors, and victim trajectories.
        """
        # 1. Compute basic fire trend (existing logic)
        basic_trend = await self._compute_fire_trend()

        # 2. Analyze camera motion
        camera_motion_detected, camera_displacement = self._analyze_camera_motion()

        # 3. Motion-corrected fire growth rate
        motion_corrected_rate = None
        if camera_motion_detected:
            motion_corrected_rate = self._correct_for_camera_motion(
                basic_trend['growth_rate'],
                camera_displacement
            )

        # 4. Depth-adjusted severity
        avg_fire_depth, depth_adjusted_severity = self._compute_depth_adjusted_severity()

        # 5. Spatial fire spread
        fire_spread_vector, fire_spread_rate = self._compute_fire_spread()

        # 6. Victim trajectories
        victim_trajectories = self._analyze_victim_trajectories()

        return SpatialTrendResult(
            # Existing fields
            severity_trend=basic_trend['trend_tag'],
            severity_growth_rate=basic_trend['growth_rate'],

            # NEW: Camera motion
            camera_motion_detected=camera_motion_detected,
            camera_displacement_meters=camera_displacement,
            motion_corrected_growth_rate=motion_corrected_rate,

            # NEW: Depth-adjusted severity
            average_fire_depth_meters=avg_fire_depth,
            depth_adjusted_severity=depth_adjusted_severity,

            # NEW: Spatial fire spread
            fire_spread_vector=fire_spread_vector,
            fire_spread_rate_meters_per_sec=fire_spread_rate,
            room_transitions=self.room_transitions.copy(),

            # NEW: Victim trajectories
            victim_trajectories=victim_trajectories,

            # Metadata
            sample_count=len(self.packet_buffer),
            time_span=self._get_time_span(),
            spatial_data_available=len(self.pose_trajectory) > 0
        )

    # =========================================================================
    # SPATIAL ANALYSIS METHODS
    # =========================================================================

    def _analyze_camera_motion(self) -> Tuple[bool, Optional[float]]:
        """
        Detect significant camera movement in buffer window.

        Returns:
            (motion_detected: bool, displacement: float in meters)
        """
        if len(self.pose_trajectory) < 2:
            return False, None

        poses = list(self.pose_trajectory)
        start_pos = poses[0]['pose'].position
        end_pos = poses[-1]['pose'].position

        # Calculate Euclidean displacement
        displacement = np.linalg.norm([
            end_pos[0] - start_pos[0],
            end_pos[1] - start_pos[1],
            end_pos[2] - start_pos[2]
        ])

        # Threshold: >0.5m movement or any WALKING/RUNNING states
        motion_states = [p['motion_state'] for p in poses]
        significant_motion = (
            displacement > 0.5 or
            any(state in ['WALKING', 'RUNNING'] for state in motion_states)
        )

        return significant_motion, displacement

    def _correct_for_camera_motion(
        self,
        raw_growth_rate: float,
        camera_displacement: float
    ) -> float:
        """
        Adjust fire growth rate to compensate for camera movement.

        Heuristic: If camera moved closer to fire, apparent growth is inflated.
        Use depth changes to normalize.
        """
        if 'fire' not in str(self.depth_history.keys()):
            return raw_growth_rate  # No fire depth data

        # Find fire depth history
        fire_depth_key = next(
            (k for k in self.depth_history.keys() if 'fire' in k),
            None
        )

        if not fire_depth_key or len(self.depth_history[fire_depth_key]) < 2:
            return raw_growth_rate

        depths = list(self.depth_history[fire_depth_key])
        start_depth = depths[0]['depth']
        end_depth = depths[-1]['depth']

        # If camera moved closer (depth decreased), fire appears larger
        depth_ratio = start_depth / end_depth if end_depth > 0 else 1.0

        # Normalize growth rate by depth change
        corrected_rate = raw_growth_rate / depth_ratio

        logger.info(
            f"Motion correction: raw={raw_growth_rate:.4f}, "
            f"depth_ratio={depth_ratio:.2f}, corrected={corrected_rate:.4f}"
        )

        return corrected_rate

    def _compute_depth_adjusted_severity(self) -> Tuple[Optional[float], Optional[float]]:
        """
        Adjust severity score based on distance to fire.

        Logic:
        - Fire < 2m away: severity × 2.0 (CRITICAL proximity)
        - Fire 2-5m away: severity × 1.0 (baseline)
        - Fire > 5m away: severity × 0.5 (distant)
        """
        fire_depths = [
            entry['depth']
            for key, history in self.depth_history.items()
            if 'fire' in key
            for entry in history
            if entry['confidence'] > 0.5  # Only high-confidence measurements
        ]

        if not fire_depths:
            return None, None

        avg_depth = np.mean(fire_depths)

        # Get latest fire_dominance score
        if not self.packet_buffer:
            return avg_depth, None

        latest_packet = self.packet_buffer[-1]
        base_severity = latest_packet.scores.fire_dominance

        # Depth-based severity multiplier
        if avg_depth < 2.0:
            multiplier = 2.0
        elif avg_depth < 5.0:
            multiplier = 1.0
        else:
            multiplier = max(0.5, 10.0 / avg_depth)  # Inverse square falloff

        adjusted_severity = min(1.0, base_severity * multiplier)

        logger.debug(
            f"Depth adjustment: depth={avg_depth:.1f}m, "
            f"base={base_severity:.2f}, adjusted={adjusted_severity:.2f}"
        )

        return avg_depth, adjusted_severity

    def _compute_fire_spread(self) -> Tuple[Optional[Tuple], Optional[float]]:
        """
        Calculate fire spread direction and rate using spatial positions.

        Returns:
            (spread_vector: (x, y, z), spread_rate: m/s)
        """
        # Extract fire positions from packet buffer
        fire_positions = []

        for packet in self.packet_buffer:
            if not packet.spatial_context:
                continue

            # Find fire object depth
            fire_key = next(
                (k for k in packet.spatial_context.object_depths.keys() if 'fire' in k),
                None
            )

            if fire_key:
                depth_obj = packet.spatial_context.object_depths[fire_key]

                # Project fire from camera position using depth
                # (Simplified: assumes fire is in front of camera)
                camera_pos = packet.spatial_context.camera_pose.position
                # TODO: More accurate projection using bbox position in frame

                fire_positions.append({
                    'timestamp': packet.timestamp,
                    'position': camera_pos  # Placeholder: needs proper projection
                })

        if len(fire_positions) < 2:
            return None, None

        # Compute spread vector (first → last position)
        start = fire_positions[0]
        end = fire_positions[-1]

        spread_vector = (
            end['position'][0] - start['position'][0],
            end['position'][1] - start['position'][1],
            end['position'][2] - start['position'][2]
        )

        time_span = end['timestamp'] - start['timestamp']
        spread_distance = np.linalg.norm(spread_vector)
        spread_rate = spread_distance / time_span if time_span > 0 else 0.0

        return spread_vector, spread_rate

    def _analyze_victim_trajectories(self) -> Dict[int, Dict]:
        """
        Track victim (person) movement over buffer window.

        Returns dict of {object_id: trajectory_analysis}
        """
        victim_trajectories = {}

        # Group packets by tracked person ID
        person_tracks = {}

        for packet in self.packet_buffer:
            if not packet.spatial_context:
                continue

            for obj in packet.tracked_objects:
                if obj.label != 'person':
                    continue

                if obj.id not in person_tracks:
                    person_tracks[obj.id] = []

                # Get person depth
                person_key = f"person_{obj.id}"
                if person_key in packet.spatial_context.object_depths:
                    depth_obj = packet.spatial_context.object_depths[person_key]
                    camera_pos = packet.spatial_context.camera_pose.position

                    person_tracks[obj.id].append({
                        'timestamp': packet.timestamp,
                        'position': camera_pos,  # Placeholder: needs bbox projection
                        'depth': depth_obj.depth_meters
                    })

        # Analyze each person's trajectory
        for person_id, track in person_tracks.items():
            if len(track) < 2:
                continue

            start = track[0]
            end = track[-1]

            displacement = np.linalg.norm([
                end['position'][0] - start['position'][0],
                end['position'][1] - start['position'][1],
                end['position'][2] - start['position'][2]
            ])

            time_span = end['timestamp'] - start['timestamp']
            velocity = (
                (end['position'][0] - start['position'][0]) / time_span,
                (end['position'][1] - start['position'][1]) / time_span,
                (end['position'][2] - start['position'][2]) / time_span
            )

            victim_trajectories[person_id] = {
                'start_position': start['position'],
                'end_position': end['position'],
                'velocity': velocity,
                'displacement_meters': displacement,
                'moving_toward_exit': False,  # TODO: Requires exit location mapping
                'moving_toward_hazard': False  # TODO: Requires hazard position
            }

        return victim_trajectories

    async def _track_room_transition(self, current_room_id: str, timestamp: float):
        """
        Detect when camera moves from one room to another.
        """
        if not self.room_transitions:
            # First room detection
            self.room_transitions.append((None, current_room_id, timestamp))
            return

        last_room = self.room_transitions[-1][1]

        if current_room_id != last_room:
            logger.info(f"Room transition: {last_room} → {current_room_id}")
            self.room_transitions.append((last_room, current_room_id, timestamp))

    # =========================================================================
    # HELPER METHODS
    # =========================================================================

    async def _evict_stale(self):
        """Evict packets older than window_seconds."""
        import time
        current_time = time.time()
        cutoff = current_time - self.window_seconds

        # Evict packets
        while self.packet_buffer and self.packet_buffer[0].timestamp < cutoff:
            self.packet_buffer.popleft()

        # Evict poses
        while self.pose_trajectory and self.pose_trajectory[0]['timestamp'] < cutoff:
            self.pose_trajectory.popleft()

        # Evict depth history
        for key in list(self.depth_history.keys()):
            while (self.depth_history[key] and
                   self.depth_history[key][0]['timestamp'] < cutoff):
                self.depth_history[key].popleft()

            # Remove empty histories
            if not self.depth_history[key]:
                del self.depth_history[key]

    def _get_time_span(self) -> float:
        """Get time span of buffered data."""
        if len(self.packet_buffer) < 2:
            return 0.0
        return self.packet_buffer[-1].timestamp - self.packet_buffer[0].timestamp

    async def _compute_fire_trend(self) -> Dict:
        """Existing fire trend computation (unchanged)."""
        # Use existing TemporalBufferAgent.compute_trend() logic
        pass  # Implementation omitted for brevity
```

---

### 4.3 RAG Service: Enhanced Narrative

```python
# FILE: fastapi/backend/agents/temporal_narrative.py (UPDATED)

def _build_timeline_prompt(self, buffer_packets: List[Dict]) -> str:
    """
    UPDATED: Include spatial progression in timeline prompt.
    """
    current_time = time.time()
    timeline = []

    for pkt in buffer_packets[-5:]:
        age = current_time - pkt["timestamp"]
        narrative = pkt["packet"].visual_narrative
        priority = pkt.get("priority", "CAUTION")

        # NEW: Add spatial context to timeline
        spatial_annotation = ""
        if pkt["packet"].spatial_context:
            spatial = pkt["packet"].spatial_context

            # Add camera motion state
            if spatial.camera_motion_state != "STATIC":
                spatial_annotation += f" [Camera: {spatial.camera_motion_state}]"

            # Add fire depth if available
            fire_depth = next(
                (d.depth_meters for k, d in spatial.object_depths.items() if 'fire' in k),
                None
            )
            if fire_depth:
                spatial_annotation += f" [Fire: {fire_depth:.1f}m away]"

            # Add room transition
            if spatial.room_id:
                spatial_annotation += f" [Room: {spatial.room_id}]"

        # Format: "T-2.3s [CRITICAL]: Major fire 45%. Path blocked. [Fire: 2.3m away]"
        timeline.append(f"T-{age:.1f}s [{priority}]: {narrative}{spatial_annotation}")

    timeline_str = "\n".join(timeline)

    prompt = f"""You are a fire safety AI analyzing temporal fire progression WITH SPATIAL AWARENESS.

INPUT - Observations (oldest → newest):
{timeline_str}

SPATIAL CONTEXT ANNOTATIONS:
- [Camera: WALKING/PANNING] = Operator is moving, fire position may appear to shift
- [Fire: X.Xm away] = Actual distance to fire (depth sensor)
- [Room: room_id] = Current location in building

TASK:
Synthesize these observations into ONE coherent narrative that captures:
1. What changed (progression/escalation) - ACCOUNTING FOR CAMERA MOTION
2. Spatial fire spread (fire moved from room A to room B)
3. Current state with distance context
4. Trajectory (pattern)

CONSTRAINTS:
- Maximum 200 characters (STRICT)
- Present tense for current state
- Past tense for progression
- No speculation, only observed facts
- Focus on safety-critical changes
- **Distinguish camera movement from fire movement**

EXAMPLES:

Input:
T-3.0s [CAUTION]: Small fire 8% [Fire: 5.2m away] [Room: kitchen]
T-2.0s [CAUTION]: Moderate fire 22% [Fire: 4.8m away] [Camera: WALKING] [Room: kitchen]
T-1.0s [HIGH]: Major fire 38% [Fire: 2.1m away] [Camera: WALKING] [Room: hallway]
T-0.0s [CRITICAL]: Major fire 45% [Fire: 2.0m away] [Room: hallway]

Output:
Fire SPREAD from kitchen to hallway in 3s. Now 2m away. Operator approached fire while moving through rooms.

Input:
T-5.0s [HIGH]: Fire 45% [Fire: 8.0m away] [Room: living_room]
T-3.0s [HIGH]: Fire 60% [Fire: 4.5m away] [Camera: WALKING]
T-1.0s [HIGH]: Fire 65% [Fire: 2.0m away] [Camera: WALKING]
T-0.0s [CRITICAL]: Fire 68% [Fire: 1.5m away] [Camera: STATIC]

Output:
Fire appears larger due to operator approaching (8m→1.5m). Actual growth: 45%→68% over 5s. Now dangerously close.

YOUR OUTPUT (200 chars max):"""

    return prompt
```

---

## 5. Frontend Dashboard Changes

### 5.1 New Component: Spatial Map View

```typescript
// FILE: frontend/src/components/SpatialMapView.tsx

import React, { useEffect, useRef } from 'react';
import { Canvas, useThree } from '@react-three/fiber';
import { OrbitControls, Line, Sphere, Text } from '@react-three/drei';

interface SpatialMapProps {
  cameraTrajectory: Array<{
    position: [number, number, number];
    timestamp: number;
  }>;
  fireLocations: Array<{
    position: [number, number, number];
    timestamp: number;
    severity: number;
  }>;
  victimTrajectories: Array<{
    personId: number;
    positions: Array<[number, number, number]>;
  }>;
}

export const SpatialMapView: React.FC<SpatialMapProps> = ({
  cameraTrajectory,
  fireLocations,
  victimTrajectories
}) => {
  return (
    <div style={{ width: '100%', height: '400px', background: '#1a1a1a' }}>
      <Canvas camera={{ position: [0, 10, 10], fov: 60 }}>
        <ambientLight intensity={0.5} />
        <pointLight position={[10, 10, 10]} />

        {/* Camera path (blue line) */}
        {cameraTrajectory.length > 1 && (
          <Line
            points={cameraTrajectory.map(c => c.position)}
            color="blue"
            lineWidth={2}
          />
        )}

        {/* Camera current position (blue sphere) */}
        {cameraTrajectory.length > 0 && (
          <Sphere
            args={[0.2]}
            position={cameraTrajectory[cameraTrajectory.length - 1].position}
          >
            <meshStandardMaterial color="blue" />
            <Text
              position={[0, 0.5, 0]}
              fontSize={0.3}
              color="white"
            >
              Camera
            </Text>
          </Sphere>
        )}

        {/* Fire locations (red spheres, size = severity) */}
        {fireLocations.map((fire, idx) => (
          <Sphere
            key={idx}
            args={[fire.severity * 0.5]}  // Larger sphere = more severe
            position={fire.position}
          >
            <meshStandardMaterial
              color="red"
              emissive="orange"
              emissiveIntensity={fire.severity}
            />
            <Text
              position={[0, 1, 0]}
              fontSize={0.3}
              color="white"
            >
              {`Fire (${fire.severity.toFixed(1)})`}
            </Text>
          </Sphere>
        ))}

        {/* Victim trajectories (green lines) */}
        {victimTrajectories.map((victim, idx) => (
          <React.Fragment key={idx}>
            <Line
              points={victim.positions}
              color="green"
              lineWidth={1.5}
            />

            {/* Victim current position */}
            {victim.positions.length > 0 && (
              <Sphere
                args={[0.15]}
                position={victim.positions[victim.positions.length - 1]}
              >
                <meshStandardMaterial color="green" />
                <Text
                  position={[0, 0.4, 0]}
                  fontSize={0.25}
                  color="white"
                >
                  {`Person ${victim.personId}`}
                </Text>
              </Sphere>
            )}
          </React.Fragment>
        ))}

        {/* Floor grid */}
        <gridHelper args={[20, 20, '#444', '#222']} />

        <OrbitControls />
      </Canvas>
    </div>
  );
};
```

### 5.2 Updated Reflex Panel (Depth-Aware Indicators)

```typescript
// FILE: frontend/src/components/ReflexPanel.tsx

interface ReflexPanelProps {
  hazardLevel: string;
  fireDominance: number;
  spatialContext?: {
    averageFireDepth?: number;
    depthAdjustedSeverity?: number;
    cameraMotionState: string;
  };
}

export const ReflexPanel: React.FC<ReflexPanelProps> = ({
  hazardLevel,
  fireDominance,
  spatialContext
}) => {
  // Determine which severity to display
  const displaySeverity = spatialContext?.depthAdjustedSeverity ?? fireDominance;
  const depthInfo = spatialContext?.averageFireDepth;

  return (
    <div className="reflex-panel">
      <h2>Hazard Level: {hazardLevel}</h2>

      {/* Severity bar */}
      <div className="severity-bar">
        <div
          className="severity-fill"
          style={{
            width: `${displaySeverity * 100}%`,
            background: getSeverityColor(displaySeverity)
          }}
        />
      </div>

      <div className="severity-label">
        Fire Dominance: {(displaySeverity * 100).toFixed(1)}%

        {/* NEW: Depth indicator */}
        {depthInfo && (
          <span className="depth-indicator">
            {` (${depthInfo.toFixed(1)}m away)`}
            {depthInfo < 2.0 && (
              <span className="proximity-warning"> ⚠️ CLOSE</span>
            )}
          </span>
        )}
      </div>

      {/* NEW: Camera motion indicator */}
      {spatialContext?.cameraMotionState !== 'STATIC' && (
        <div className="camera-motion-badge">
          📹 Camera {spatialContext.cameraMotionState}
        </div>
      )}

      {/* NEW: Motion correction notice */}
      {spatialContext?.depthAdjustedSeverity !== fireDominance && (
        <div className="adjustment-notice">
          <small>
            Severity adjusted for distance
            (raw: {(fireDominance * 100).toFixed(1)}%)
          </small>
        </div>
      )}
    </div>
  );
};

function getSeverityColor(severity: number): string {
  if (severity > 0.6) return '#d32f2f';  // Red
  if (severity > 0.3) return '#f57c00';  // Orange
  return '#fbc02d';  // Yellow
}
```

---

## 6. Database Schema Changes

### 6.1 Incident Log Table (Add Spatial Columns)

```sql
-- FILE: fastapi/db/migrations/003_add_spatial_columns.sql

-- Add spatial context columns to incident_log
ALTER TABLE incident_log ADD COLUMN IF NOT EXISTS camera_position_x FLOAT;
ALTER TABLE incident_log ADD COLUMN IF NOT EXISTS camera_position_y FLOAT;
ALTER TABLE incident_log ADD COLUMN IF NOT EXISTS camera_position_z FLOAT;

ALTER TABLE incident_log ADD COLUMN IF NOT EXISTS camera_orientation_w FLOAT;
ALTER TABLE incident_log ADD COLUMN IF NOT EXISTS camera_orientation_x FLOAT;
ALTER TABLE incident_log ADD COLUMN IF NOT EXISTS camera_orientation_y FLOAT;
ALTER TABLE incident_log ADD COLUMN IF NOT EXISTS camera_orientation_z FLOAT;

ALTER TABLE incident_log ADD COLUMN IF NOT EXISTS average_fire_depth FLOAT;
ALTER TABLE incident_log ADD COLUMN IF NOT EXISTS depth_adjusted_severity FLOAT;
ALTER TABLE incident_log ADD COLUMN IF NOT EXISTS camera_motion_state VARCHAR(20);
ALTER TABLE incident_log ADD COLUMN IF NOT EXISTS room_id VARCHAR(50);

-- Add index for spatial queries (room-based incident retrieval)
CREATE INDEX IF NOT EXISTS idx_incident_room ON incident_log (room_id, timestamp);

-- Add index for depth-based filtering
CREATE INDEX IF NOT EXISTS idx_incident_depth ON incident_log (average_fire_depth)
  WHERE average_fire_depth IS NOT NULL;
```

### 6.2 Incident Logger Agent Update

```python
# FILE: fastapi/backend/agents/incident_logger.py

async def log_incident(
    self,
    packet: TelemetryPacket,
    narrative_vector: List[float],
    trend: SpatialTrendResult
):
    """
    UPDATED: Log spatial context to incident_log.
    """
    # Existing fields
    incident = {
        'timestamp': packet.timestamp,
        'session_id': packet.session_id,
        'device_id': packet.device_id,
        'narrative_vector': narrative_vector,
        'raw_narrative': packet.visual_narrative,
        'trend_tag': trend.severity_trend,
        'hazard_level': packet.hazard_level,
        'fire_dominance': packet.scores.fire_dominance,
        'smoke_opacity': packet.scores.smoke_opacity,
        'proximity_alert': packet.scores.proximity_alert,
    }

    # NEW: Add spatial context fields
    if packet.spatial_context:
        pose = packet.spatial_context.camera_pose
        incident.update({
            'camera_position_x': pose.position[0],
            'camera_position_y': pose.position[1],
            'camera_position_z': pose.position[2],
            'camera_orientation_w': pose.orientation[0],
            'camera_orientation_x': pose.orientation[1],
            'camera_orientation_y': pose.orientation[2],
            'camera_orientation_z': pose.orientation[3],
            'average_fire_depth': trend.average_fire_depth_meters,
            'depth_adjusted_severity': trend.depth_adjusted_severity,
            'camera_motion_state': packet.spatial_context.camera_motion_state,
            'room_id': packet.spatial_context.room_id
        })

    await self.batch_writer.add_incident(incident)
```

---

## 7. Implementation Timeline

### Week 1: iPhone Edge Device (Days 1-5)

<function_calls>
<invoke name="TodoWrite">
<parameter name="todos">[{"content": "Design spatial context data model and schema changes", "status": "completed", "activeForm": "Designing spatial context data model and schema changes"}, {"content": "Document changes to Nano/iPhone edge device", "status": "completed", "activeForm": "Documenting changes to Nano/iPhone edge device"}, {"content": "Document changes to backend pipeline (ingest, temporal buffer, RAG)", "status": "completed", "activeForm": "Documenting changes to backend pipeline"}, {"content": "Document changes to frontend dashboard", "status": "completed", "activeForm": "Documenting changes to frontend dashboard"}, {"content": "Create implementation timeline and task breakdown", "status": "in_progress", "activeForm": "Creating implementation timeline and task breakdown"}]