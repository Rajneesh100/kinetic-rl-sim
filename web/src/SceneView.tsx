import { useEffect, useRef } from "react";
import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import type { Geom, Snapshot } from "./types";

type Props = {
  state: Snapshot | null;
  robot: string;
  track: boolean;
  selected: string;
  view: "orbit" | "top" | "follow";
  followTarget: string | null;
  cameraReset: number;
  grid: boolean;
  onSelect: (name: string) => void;
};
export default function SceneView({
  state,
  robot,
  track,
  selected,
  view,
  followTarget,
  cameraReset,
  grid,
  onSelect,
}: Props) {
  const mount = useRef<HTMLDivElement>(null);
  const data = useRef({
    state, robot, track, selected, view, followTarget, cameraReset, grid, onSelect,
  });
  data.current = {
    state, robot, track, selected, view, followTarget, cameraReset, grid, onSelect,
  };
  useEffect(() => {
    if (!mount.current) return;
    const host = mount.current;
    const scene = new THREE.Scene();
    scene.background = new THREE.Color("#bcc6c0");
    scene.fog = new THREE.Fog("#bcc6c0", 70, 190);
    const camera = new THREE.PerspectiveCamera(42, 1, 0.05, 600);
    camera.up.set(0, 0, 1);
    camera.position.set(-17, -24, 19);
    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.shadowMap.enabled = true;
    renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 1.35;
    host.appendChild(renderer.domElement);
    const controls = new OrbitControls(camera, renderer.domElement);
    controls.target.set(7, 0, 0);
    controls.enableDamping = true;
    controls.dampingFactor = 0.08;
    controls.maxPolarAngle = Math.PI * 0.48;
    controls.minDistance = 3;
    controls.maxDistance = 160;
    scene.add(new THREE.HemisphereLight(0xecf6ff, 0x636c58, 2.3));
    const sun = new THREE.DirectionalLight(0xfff5de, 3.8);
    sun.position.set(-20, -25, 40);
    sun.castShadow = true;
    sun.shadow.mapSize.set(2048, 2048);
    sun.shadow.camera.left = -70;
    sun.shadow.camera.right = 70;
    sun.shadow.camera.top = 70;
    sun.shadow.camera.bottom = -70;
    sun.shadow.camera.far = 150;
    sun.shadow.normalBias = 0.018;
    sun.shadow.bias = -0.00015;
    scene.add(sun);
    const ground = new THREE.Mesh(
      new THREE.PlaneGeometry(400, 400),
      new THREE.MeshStandardMaterial({ color: "#a5b2a6", roughness: 0.97 }),
    );
    ground.position.z = -0.03;
    ground.receiveShadow = true;
    scene.add(ground);
    const helper = new THREE.GridHelper(220, 110, 0x78897c, 0x91a191);
    helper.rotation.x = Math.PI / 2;
    helper.position.z = 0.006;
    (helper.material as THREE.Material).transparent = true;
    (helper.material as THREE.Material).opacity = 0.25;
    scene.add(helper);
    const road = new THREE.Group();
    const roadSurface = new THREE.Mesh(
      new THREE.PlaneGeometry(80, 8),
      new THREE.MeshStandardMaterial({ color: "#3d4547", roughness: 0.99 }),
    );
    roadSurface.position.set(25, 0, 0.012);
    roadSurface.receiveShadow = true;
    road.add(roadSurface);
    const roadPaint = new THREE.MeshStandardMaterial({
      color: "#e8e4cc",
      roughness: 1,
    });
    for (let x = -13; x < 65; x += 5) {
      const dash = new THREE.Mesh(new THREE.PlaneGeometry(2, 0.085), roadPaint);
      dash.position.set(x, 0, 0.022);
      road.add(dash);
    }
    for (const y of [-3.7, 3.7]) {
      const edge = new THREE.Mesh(new THREE.PlaneGeometry(80, 0.1), roadPaint);
      edge.position.set(25, y, 0.022);
      road.add(edge);
    }
    scene.add(road);
    const meshes = new Map<number, THREE.Mesh>();
    let lastView = "";
    let lastRobot = "";
    let lastCameraReset = -1;
    const followPosition = new THREE.Vector3();
    const followDelta = new THREE.Vector3();
    let frame = 0;
    let lastState: Snapshot | null = null;
    let selectedBox: THREE.BoxHelper | null = null;
    function geometry(g: Geom): THREE.BufferGeometry {
      switch (g.type) {
        case "plane":
          return new THREE.PlaneGeometry(
            (g.size[0] || 100) * 2,
            (g.size[1] || 100) * 2,
          );
        case "sphere":
          return new THREE.SphereGeometry(g.size[0], 28, 20);
        case "ellipsoid": {
          const shape = new THREE.SphereGeometry(1, 28, 20);
          shape.scale(...g.size);
          return shape;
        }
        case "cylinder": {
          const shape = new THREE.CylinderGeometry(
            g.size[0],
            g.size[0],
            g.size[1] * 2,
            28,
          );
          shape.rotateX(Math.PI / 2);
          return shape;
        }
        case "capsule": {
          const shape = new THREE.CapsuleGeometry(
            g.size[0],
            g.size[1] * 2,
            8,
            20,
          );
          shape.rotateX(Math.PI / 2);
          return shape;
        }
        default:
          return new THREE.BoxGeometry(
            g.size[0] * 2,
            g.size[1] * 2,
            g.size[2] * 2,
          );
      }
    }
    function resize() {
      const { width, height } = host.getBoundingClientRect();
      if (width === 0 || height === 0) return;
      renderer.setSize(width, height);
      camera.aspect = width / height;
      camera.updateProjectionMatrix();
    }
    const observer = new ResizeObserver(resize);
    observer.observe(host);
    resize();
    const raycaster = new THREE.Raycaster();
    const mouse = new THREE.Vector2();
    let pointerStart = [0, 0];
    function down(e: PointerEvent) {
      pointerStart = [e.clientX, e.clientY];
    }
    function click(e: PointerEvent) {
      if (
        Math.hypot(e.clientX - pointerStart[0], e.clientY - pointerStart[1]) > 5
      )
        return;
      const r = host.getBoundingClientRect();
      mouse.set(
        ((e.clientX - r.left) / r.width) * 2 - 1,
        -((e.clientY - r.top) / r.height) * 2 + 1,
      );
      raycaster.setFromCamera(mouse, camera);
      const hits = raycaster.intersectObjects([...meshes.values()]);
      if (hits[0]) data.current.onSelect(hits[0].object.userData.name);
    }
    renderer.domElement.addEventListener("pointerdown", down);
    renderer.domElement.addEventListener("pointerup", click);
    function animate() {
      frame = requestAnimationFrame(animate);
      const current = data.current;
      road.visible = current.track;
      helper.visible = current.grid;
      if (current.robot !== lastRobot) {
        lastRobot = current.robot;
        lastView = "";
      }
      controls.enablePan = current.view !== "follow";
      if (
        !lastView ||
        current.cameraReset !== lastCameraReset ||
        (current.view === "top" && lastView !== "top") ||
        (current.view === "orbit" && lastView === "top")
      ) {
        const subject = current.state?.geoms.find((g) =>
          current.view === "follow"
            ? g.name === current.followTarget
            : /^(robot_chassis|robot_torso|robot_fuselage)$/.test(g.name),
        );
        const target = subject
          ? new THREE.Vector3(...subject.position)
          : new THREE.Vector3(0, 1, 1);
        if (current.robot === "car") target.x += 3.5;
        if (current.robot === "quadruped") target.x += 1;
        controls.target.copy(target);
        if (current.view === "top") {
          camera.position
            .copy(target)
            .add(
              new THREE.Vector3(0, -0.01, current.robot === "car" ? 44 : 20),
            );
        } else {
          camera.position
            .copy(target)
            .add(
              current.robot === "car"
                ? new THREE.Vector3(-11, -14, 12)
                : current.robot === "aircraft"
                  ? new THREE.Vector3(-8, -10, 6)
                  : new THREE.Vector3(-5, -6, 4.5),
            );
        }
        camera.lookAt(target);
      }
      lastView = current.view;
      lastCameraReset = current.cameraReset;
      if (current.state && current.state !== lastState) {
        lastState = current.state;
        const live = new Set<number>();
        for (const geom of current.state.geoms) {
          live.add(geom.id);
          let mesh = meshes.get(geom.id);
          const key = geom.type + geom.size.join(",");
          if (mesh && mesh.userData.key !== key) {
            scene.remove(mesh);
            mesh.geometry.dispose();
            (mesh.material as THREE.Material).dispose();
            meshes.delete(geom.id);
            mesh = undefined;
          }
          if (!mesh) {
            mesh = new THREE.Mesh(
              geometry(geom),
              new THREE.MeshStandardMaterial({
                color: new THREE.Color(
                  geom.rgba[0],
                  geom.rgba[1],
                  geom.rgba[2],
                ),
                roughness: 0.64,
                metalness: geom.name.includes("wheel") ? 0.15 : 0.08,
                transparent: geom.rgba[3] < 1,
                opacity: geom.rgba[3],
              }),
            );
            mesh.userData = { name: geom.name, key };
            mesh.castShadow = geom.type !== "plane";
            mesh.receiveShadow = true;
            meshes.set(geom.id, mesh);
            scene.add(mesh);
          }
          mesh.userData.name = geom.name;
          mesh.position.set(...geom.position);
          mesh.quaternion.set(
            geom.quaternion[1],
            geom.quaternion[2],
            geom.quaternion[3],
            geom.quaternion[0],
          );
          if (geom.type === "plane") {
            mesh.position.z -= 0.015;
            mesh.receiveShadow = true;
          }
          const material = mesh.material as THREE.MeshStandardMaterial;
          material.color.setRGB(geom.rgba[0], geom.rgba[1], geom.rgba[2]);
        }
        for (const [id, mesh] of meshes) {
          if (!live.has(id)) {
            scene.remove(mesh);
            mesh.geometry.dispose();
            (mesh.material as THREE.Material).dispose();
            meshes.delete(id);
          }
        }
      }
      if (selectedBox) {
        scene.remove(selectedBox);
        selectedBox.geometry.dispose();
        (selectedBox.material as THREE.Material).dispose();
        selectedBox = null;
      }
      const object = [...meshes.values()].find(
        (m) =>
          m.userData.name === current.selected ||
          m.userData.name === current.selected + "_geom" ||
          (current.selected === "robot" &&
            /chassis|torso|fuselage/.test(m.userData.name)),
      );
      if (object) {
        selectedBox = new THREE.BoxHelper(object, 0xff8258);
        scene.add(selectedBox);
      }
      controls.update();
      if (current.view === "follow" && current.followTarget && current.state) {
        const geom = current.state.geoms.find(
          (g) => g.name === current.followTarget,
        );
        if (geom) {
          // Translate camera and pivot together, preserving the user's orbit/zoom.
          // Apply after controls.update() to cancel any residual pan damping.
          followPosition.set(...geom.position);
          followDelta.subVectors(followPosition, controls.target);
          camera.position.add(followDelta);
          controls.target.copy(followPosition);
        }
      }
      renderer.render(scene, camera);
    }
    animate();
    return () => {
      cancelAnimationFrame(frame);
      observer.disconnect();
      controls.dispose();
      renderer.domElement.removeEventListener("pointerdown", down);
      renderer.domElement.removeEventListener("pointerup", click);
      scene.traverse((o) => {
        if (o instanceof THREE.Mesh) {
          o.geometry.dispose();
          if (Array.isArray(o.material)) o.material.forEach((m) => m.dispose());
          else o.material.dispose();
        }
      });
      renderer.dispose();
      host.removeChild(renderer.domElement);
    };
  }, []);
  return (
    <div
      className="three-mount"
      ref={mount}
      aria-label="Interactive 3D simulation scene"
    />
  );
}
