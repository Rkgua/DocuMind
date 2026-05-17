function RobotAvatar({ status = "idle-relax-1", size = 500, onClick }) {
  const srcMap = {
    entrance: "/待机2-发光.gif",
    "idle-relax-1": "/待机1-放松.gif",
    thinking: "/闪亮登场.gif",
    "idle-glow-2": "/待机2-发光.gif",
  };
  return (
    <img
      src={srcMap[status] || srcMap["idle-relax-1"]}
      alt=""
      draggable={false}
      onClick={onClick}
      style={{
        width: size,
        height: size,
        objectFit: "contain",
        display: "block",
        borderRadius: 8,
        cursor: "pointer",
      }}
    />
  );
}

export default RobotAvatar;
