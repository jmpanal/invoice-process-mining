declare module 'bpmn-js/lib/NavigatedViewer' {
  type Canvas = {
    zoom(value: 'fit-viewport'): void;
  };

  type Viewer = {
    importXML(xml: string): Promise<{ warnings: unknown[] }>;
    get(name: 'canvas'): Canvas;
    destroy(): void;
  };

  const BpmnViewer: new (options: { container: HTMLElement }) => Viewer;
  export default BpmnViewer;
}
