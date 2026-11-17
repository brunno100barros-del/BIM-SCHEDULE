import React, { useRef, useEffect, useState } from 'react';
import * as THREE from 'three';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';
import { IFCLoader } from 'web-ifc-three/IFCLoader';

interface IfcViewerProps { ifcUrl: string | null; requestHeaders?: Record<string, string> }
export const IfcViewer: React.FC<IfcViewerProps> = ({ ifcUrl, requestHeaders }) => {
  // Chave estável: o objeto de cabeçalhos é recriado a cada renderização.
  const headersKey = JSON.stringify(requestHeaders ?? {});
  const containerRef = useRef<HTMLDivElement>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    const container = containerRef.current;
    if (!container || !ifcUrl) { setLoading(false); setError(''); return; }
    let disposed = false;
    let frameId = 0;
    let loadedModel: any = null;
    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x0f172a);
    const width = Math.max(container.clientWidth, 1);
    const height = Math.max(container.clientHeight, 1);
    const camera = new THREE.PerspectiveCamera(55, width / height, 0.1, 100000);
    camera.position.set(15, 15, 15);
    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    renderer.setSize(width, height);
    container.replaceChildren(renderer.domElement);
    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    scene.add(new THREE.AmbientLight(0xffffff, 0.75));
    const directional = new THREE.DirectionalLight(0xffffff, 1.1);
    directional.position.set(10, 20, 10); scene.add(directional);
    const grid = new THREE.GridHelper(100, 100, 0x334155, 0x1e293b); scene.add(grid);
    const loader = new IFCLoader();
    // Caminho relativo à aplicação: funciona no Vite, em subpastas e em file:// (Electron).
    loader.ifcManager.setWasmPath(import.meta.env.BASE_URL);
    loader.setRequestHeader(JSON.parse(headersKey));
    setLoading(true); setError('');

    loader.load(ifcUrl, (model) => {
      if (disposed) {
        try { loader.ifcManager.close(model.modelID); } catch { /* model already disposed */ }
        return;
      }
      loadedModel = model;
      scene.add(model);
      const bounds = new THREE.Box3().setFromObject(model);
      if (!bounds.isEmpty()) {
        const center = bounds.getCenter(new THREE.Vector3());
        const size = bounds.getSize(new THREE.Vector3());
        const maxDim = Math.max(size.x, size.y, size.z, 1);
        controls.target.copy(center);
        camera.position.set(center.x + maxDim * 1.4, center.y + maxDim * 1.1, center.z + maxDim * 1.4);
        camera.near = Math.max(maxDim / 10000, 0.01);
        camera.far = maxDim * 100;
        camera.updateProjectionMatrix();
      }
      setLoading(false);
    }, (event) => {
      if (event.total > 0) setLoading(true);
    }, (loadError) => {
      if (!disposed) { setLoading(false); setError(`Falha ao carregar o IFC: ${String(loadError)}`); }
    });

    const animate = () => {
      if (disposed) return;
      frameId = requestAnimationFrame(animate);
      controls.update(); renderer.render(scene, camera);
    };
    animate();
    const resizeObserver = new ResizeObserver(() => {
      if (disposed) return;
      const w = Math.max(container.clientWidth, 1); const h = Math.max(container.clientHeight, 1);
      camera.aspect = w / h; camera.updateProjectionMatrix(); renderer.setSize(w, h);
    });
    resizeObserver.observe(container);

    return () => {
      disposed = true; cancelAnimationFrame(frameId); resizeObserver.disconnect(); controls.dispose();
      if (loadedModel) {
        scene.remove(loadedModel);
        try { loader.ifcManager.close(loadedModel.modelID); } catch { /* ignore cleanup errors */ }
      }
      scene.traverse(object => {
        const mesh = object as THREE.Mesh;
        if (mesh.geometry) mesh.geometry.dispose();
        const materials = Array.isArray(mesh.material) ? mesh.material : mesh.material ? [mesh.material] : [];
        materials.forEach(material => material.dispose());
      });
      renderer.dispose(); renderer.domElement.remove();
    };
  }, [ifcUrl, headersKey]);

  return <div className="w-full h-full min-h-[420px] relative border border-slate-700 rounded-xl overflow-hidden bg-slate-900 shadow-inner">
    {!ifcUrl && <div className="absolute inset-0 flex items-center justify-center text-slate-500 text-sm font-medium">Selecione ou faça upload de um modelo IFC para visualizar.</div>}
    {loading && ifcUrl && <div className="absolute top-3 left-3 z-10 px-3 py-2 rounded-lg bg-slate-950/90 border border-slate-700 text-xs text-slate-200">Carregando geometria IFC…</div>}
    {error && <div className="absolute top-3 left-3 right-3 z-10 px-3 py-2 rounded-lg bg-red-950/90 border border-red-700 text-xs text-red-200">{error}</div>}
    <div ref={containerRef} className="w-full h-full" />
  </div>;
};
