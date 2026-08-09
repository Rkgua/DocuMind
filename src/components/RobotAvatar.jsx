function RobotAvatar({ status = "idle", size = 500, onClick }) {
  const srcMap = {
    entrance: "/robot/robot-entrance.gif?v=3",
    idle: "/robot/robot-idle.gif?v=3",
    listening: "/robot/robot-listening.gif?v=3",
    thinking: "/robot/robot-thinking.gif?v=3",
    responding: "/robot/robot-responding.gif?v=3",
    success: "/robot/robot-success.gif?v=3",
    error: "/robot/robot-error.gif?v=3",
  };
  return (
    <img
      src={srcMap[status] || srcMap.idle}
      alt="DocuMind 机器人"
      draggable={false}
      onClick={onClick}
      style={{
        width: size,
        height: size,
        objectFit: "contain",
        display: "block",
        borderRadius: 8,
        cursor: onClick ? "pointer" : "default",
      }}
    />
  );
}

export default RobotAvatar;
