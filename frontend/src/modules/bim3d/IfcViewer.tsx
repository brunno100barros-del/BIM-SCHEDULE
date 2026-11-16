import React, { useRef, useEffect } from 'react';
import * as THREE from 'three';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls';
import { IFCLoader } from 'web-ifc-three/IFCLoader';

interface IfcViewerProps {
  ifcUrl: string | null;
}

export const IfcViewer: React.FC<IfcViewerProps> = ({ ifcUrl }) => {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!containerRef.current || !ifcUrl) return;

    const container = containerRef.current;
    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x0f172a);

    const camera = new THREE.PerspectiveCamera(75, container.clientWidth / container.clientHeight, 0.1, 1000);
    camera.position.set(15, 15, 15);

    const renderer = new THREE.WebGLRenderer({ antialias: true });
    renderer.setSize(container.clientWidth, container.clientHeight);
    container.innerHTML = '';
    container.appendChild(renderer.domElement);

    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    
    const ambientLight = new THREE.AmbientLight(0xffffff, 0.6);
    scene.add(ambientLight);
    const directionalLight = new THREE.DirectionalLight(0xffffff, 1);
    directionalLight.position.set(10, 20, 10);
    scene.add(directionalLight);

    const ifcLoader = new IFCLoader();
    ifcLoader.ifcManager.setWasmPath('/');
    
    ifcLoader.load(ifcUrl, (ifcModel) => {
      scene.add(ifcModel);
      const box = new THREE.Box3().setFromObject(ifcModel);
      const center = box.getCenter(new THREE.Vector3());
      controls.target.copy(center);
      camera.position.set(center.x + 20, center.y + 15, center.z + 20);
    });

    const animate = () => {
      requestAnimationFrame(animate);
      controls.update();
      renderer.render(scene, camera);
    };
    animate();

    const handleResize = () => {
      camera.aspect = container.clientWidth / container.clientHeight;
      camera.updateProjectionMatrix();
      renderer.setSize(container.clientWidth, container.clientHeight);
    };
    window.addEventListener('resize', handleResize);

    return () => {
      window.removeEventListener('resize', handleResize);
      renderer.dispose();
    };
  }, [ifcUrl]);

  return (
    <div className="w-full h-full relative border border-slate-700 rounded-xl overflow-hidden bg-slate-900 shadow-inner">
      {!ifcUrl && (
        <div className="absolute inset-0 flex items-center justify-center text-slate-500 text-sm font-medium">
          Selecione ou faça upload de um modelo IFC para visualizar.
        </div>
      )}
      <div ref={containerRef} className="w-full h-full" />
    </div>
  );
};
