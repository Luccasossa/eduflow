-- phpMyAdmin SQL Dump
-- version 5.2.1
-- https://www.phpmyadmin.net/
--
-- Servidor: localhost
-- Tiempo de generación: 13-10-2026 a las 02:02:27
-- Versión del servidor: 10.4.32-MariaDB
-- Versión de PHP: 8.2.12

SET SQL_MODE = "NO_AUTO_VALUE_ON_ZERO";
START TRANSACTION;
SET time_zone = "+00:00";


/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!40101 SET NAMES utf8mb4 */;

--
-- Base de datos: `EduFlow`
--

-- --------------------------------------------------------

--
-- Estructura de tabla para la tabla `Alumno`
--

CREATE TABLE `Alumno` (
  `ID_Usuario` int(10) UNSIGNED NOT NULL,
  `ID_Alumno` int(10) UNSIGNED NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

--
-- Volcado de datos para la tabla `Alumno`
--

INSERT INTO `Alumno` (`ID_Usuario`, `ID_Alumno`) VALUES
(2, 1);

-- --------------------------------------------------------

--
-- Estructura de tabla para la tabla `Archivo`
--

CREATE TABLE `Archivo` (
  `ID_Archivo` int(10) UNSIGNED NOT NULL,
  `ID_Tipo` int(10) UNSIGNED NOT NULL,
  `ID_Alumno` int(10) UNSIGNED NOT NULL,
  `Nombre` varchar(200) NOT NULL,
  `Ruta` varchar(500) NOT NULL,
  `Tamano` bigint(20) UNSIGNED NOT NULL DEFAULT 0,
  `Fecha_Subida` datetime NOT NULL DEFAULT current_timestamp()
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

--
-- Volcado de datos para la tabla `Archivo`
--

INSERT INTO `Archivo` (`ID_Archivo`, `ID_Tipo`, `ID_Alumno`, `Nombre`, `Ruta`, `Tamano`, `Fecha_Subida`) VALUES
(1, 1, 1, 'Trabajo practico', 'uploads/trabajo.pdf', 250000, '2026-10-12 19:10:14');

-- --------------------------------------------------------

--
-- Estructura de tabla para la tabla `Cursa`
--

CREATE TABLE `Cursa` (
  `ID_Alumno` int(10) UNSIGNED NOT NULL,
  `ID_Materia` int(10) UNSIGNED NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

--
-- Volcado de datos para la tabla `Cursa`
--

INSERT INTO `Cursa` (`ID_Alumno`, `ID_Materia`) VALUES
(1, 1);

-- --------------------------------------------------------

--
-- Estructura de tabla para la tabla `Materias`
--

CREATE TABLE `Materias` (
  `ID_Materia` int(10) UNSIGNED NOT NULL,
  `ID_Profesor` int(10) UNSIGNED NOT NULL,
  `Nombre` varchar(120) NOT NULL,
  `Descripcion` text DEFAULT NULL,
  `Anio` smallint(5) UNSIGNED NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

--
-- Volcado de datos para la tabla `Materias`
--

INSERT INTO `Materias` (`ID_Materia`, `ID_Profesor`, `Nombre`, `Descripcion`, `Anio`) VALUES
(1, 1, 'Bases de Datos I', 'Introduccion al modelo relacional y SQL', 2026);

-- --------------------------------------------------------

--
-- Estructura de tabla para la tabla `Participa`
--

CREATE TABLE `Participa` (
  `ID_Alumno` int(10) UNSIGNED NOT NULL,
  `ID_Proyecto` int(10) UNSIGNED NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

--
-- Volcado de datos para la tabla `Participa`
--

INSERT INTO `Participa` (`ID_Alumno`, `ID_Proyecto`) VALUES
(1, 1);

-- --------------------------------------------------------

--
-- Estructura de tabla para la tabla `Profesor`
--

CREATE TABLE `Profesor` (
  `ID_Usuario` int(10) UNSIGNED NOT NULL,
  `ID_Profesor` int(10) UNSIGNED NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

--
-- Volcado de datos para la tabla `Profesor`
--

INSERT INTO `Profesor` (`ID_Usuario`, `ID_Profesor`) VALUES
(1, 1);

-- --------------------------------------------------------

--
-- Estructura de tabla para la tabla `Proyecto`
--

CREATE TABLE `Proyecto` (
  `ID_Proyecto` int(10) UNSIGNED NOT NULL,
  `ID_Materia` int(10) UNSIGNED NOT NULL,
  `Nombre` varchar(150) NOT NULL,
  `Descripcion` text DEFAULT NULL,
  `Estado` enum('Pendiente','En progreso','Completado') NOT NULL DEFAULT 'Pendiente',
  `Fecha_Creacion` datetime NOT NULL DEFAULT current_timestamp(),
  `Fecha_Entrega` date DEFAULT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

--
-- Volcado de datos para la tabla `Proyecto`
--

INSERT INTO `Proyecto` (`ID_Proyecto`, `ID_Materia`, `Nombre`, `Descripcion`, `Estado`, `Fecha_Creacion`, `Fecha_Entrega`) VALUES
(1, 1, 'Proyecto EduFlow', 'Desarrollo de una plataforma academica', 'En progreso', '2026-10-12 19:09:34', '2026-12-01');

-- --------------------------------------------------------

--
-- Estructura de tabla para la tabla `Tarea`
--

CREATE TABLE `Tarea` (
  `ID_Tarea` int(10) UNSIGNED NOT NULL,
  `ID_Proyecto` int(10) UNSIGNED NOT NULL,
  `Estado` enum('Pendiente','En progreso','Completada') NOT NULL DEFAULT 'Pendiente',
  `Prioridad` enum('Baja','Media','Alta') NOT NULL DEFAULT 'Media',
  `Titulo` varchar(150) NOT NULL,
  `Descripcion` text DEFAULT NULL,
  `Fecha_Vencimiento` date DEFAULT NULL,
  `Fecha_Creacion` datetime NOT NULL DEFAULT current_timestamp()
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

--
-- Volcado de datos para la tabla `Tarea`
--

INSERT INTO `Tarea` (`ID_Tarea`, `ID_Proyecto`, `Estado`, `Prioridad`, `Titulo`, `Descripcion`, `Fecha_Vencimiento`, `Fecha_Creacion`) VALUES
(1, 1, 'Pendiente', 'Alta', 'Crear la base de datos', 'Definir tablas y relaciones en MySQL', '2026-10-20', '2026-10-12 19:09:53');

-- --------------------------------------------------------

--
-- Estructura de tabla para la tabla `Tipo`
--

CREATE TABLE `Tipo` (
  `ID_Tipo` int(10) UNSIGNED NOT NULL,
  `Nombre` varchar(50) NOT NULL,
  `Extension` varchar(15) NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

--
-- Volcado de datos para la tabla `Tipo`
--

INSERT INTO `Tipo` (`ID_Tipo`, `Nombre`, `Extension`) VALUES
(1, 'Documento PDF', '.pdf');

-- --------------------------------------------------------

--
-- Estructura de tabla para la tabla `Usuario`
--

CREATE TABLE `Usuario` (
  `ID_Usuario` int(10) UNSIGNED NOT NULL,
  `Nombre` varchar(80) NOT NULL,
  `Apellido` varchar(80) NOT NULL,
  `Clave` varchar(255) NOT NULL,
  `Email` varchar(150) NOT NULL,
  `Dni` varchar(20) NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

--
-- Volcado de datos para la tabla `Usuario`
--

INSERT INTO `Usuario` (`ID_Usuario`, `Nombre`, `Apellido`, `Clave`, `Email`, `Dni`) VALUES
(1, 'Carlos', 'Gomez', 'hash_de_ejemplo_1', 'carlos@eduflow.test', '40000001'),
(2, 'Lucia', 'Perez', 'hash_de_ejemplo_2', 'lucia@eduflow.test', '40000002');

-- --------------------------------------------------------

--
-- Estructura de tabla para la tabla `Visualiza`
--

CREATE TABLE `Visualiza` (
  `ID_Profesor` int(10) UNSIGNED NOT NULL,
  `ID_Tarea` int(10) UNSIGNED NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

--
-- Volcado de datos para la tabla `Visualiza`
--

INSERT INTO `Visualiza` (`ID_Profesor`, `ID_Tarea`) VALUES
(1, 1);

--
-- Índices para tablas volcadas
--

--
-- Indices de la tabla `Alumno`
--
ALTER TABLE `Alumno`
  ADD PRIMARY KEY (`ID_Usuario`),
  ADD UNIQUE KEY `ID_Alumno` (`ID_Alumno`);

--
-- Indices de la tabla `Archivo`
--
ALTER TABLE `Archivo`
  ADD PRIMARY KEY (`ID_Archivo`),
  ADD KEY `fk_archivo_tipo` (`ID_Tipo`),
  ADD KEY `fk_archivo_alumno` (`ID_Alumno`);

--
-- Indices de la tabla `Cursa`
--
ALTER TABLE `Cursa`
  ADD PRIMARY KEY (`ID_Alumno`,`ID_Materia`),
  ADD KEY `fk_cursa_materia` (`ID_Materia`);

--
-- Indices de la tabla `Materias`
--
ALTER TABLE `Materias`
  ADD PRIMARY KEY (`ID_Materia`),
  ADD KEY `fk_materia_profesor` (`ID_Profesor`);

--
-- Indices de la tabla `Participa`
--
ALTER TABLE `Participa`
  ADD PRIMARY KEY (`ID_Alumno`,`ID_Proyecto`),
  ADD KEY `fk_participa_proyecto` (`ID_Proyecto`);

--
-- Indices de la tabla `Profesor`
--
ALTER TABLE `Profesor`
  ADD PRIMARY KEY (`ID_Usuario`),
  ADD UNIQUE KEY `ID_Profesor` (`ID_Profesor`);

--
-- Indices de la tabla `Proyecto`
--
ALTER TABLE `Proyecto`
  ADD PRIMARY KEY (`ID_Proyecto`),
  ADD KEY `fk_proyecto_materia` (`ID_Materia`);

--
-- Indices de la tabla `Tarea`
--
ALTER TABLE `Tarea`
  ADD PRIMARY KEY (`ID_Tarea`),
  ADD KEY `fk_tarea_proyecto` (`ID_Proyecto`);

--
-- Indices de la tabla `Tipo`
--
ALTER TABLE `Tipo`
  ADD PRIMARY KEY (`ID_Tipo`),
  ADD UNIQUE KEY `Nombre` (`Nombre`,`Extension`);

--
-- Indices de la tabla `Usuario`
--
ALTER TABLE `Usuario`
  ADD PRIMARY KEY (`ID_Usuario`),
  ADD UNIQUE KEY `Email` (`Email`),
  ADD UNIQUE KEY `Dni` (`Dni`);

--
-- Indices de la tabla `Visualiza`
--
ALTER TABLE `Visualiza`
  ADD PRIMARY KEY (`ID_Profesor`,`ID_Tarea`),
  ADD KEY `fk_visualiza_tarea` (`ID_Tarea`);

--
-- AUTO_INCREMENT de las tablas volcadas
--

--
-- AUTO_INCREMENT de la tabla `Alumno`
--
ALTER TABLE `Alumno`
  MODIFY `ID_Alumno` int(10) UNSIGNED NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=2;

--
-- AUTO_INCREMENT de la tabla `Archivo`
--
ALTER TABLE `Archivo`
  MODIFY `ID_Archivo` int(10) UNSIGNED NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=2;

--
-- AUTO_INCREMENT de la tabla `Materias`
--
ALTER TABLE `Materias`
  MODIFY `ID_Materia` int(10) UNSIGNED NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=2;

--
-- AUTO_INCREMENT de la tabla `Profesor`
--
ALTER TABLE `Profesor`
  MODIFY `ID_Profesor` int(10) UNSIGNED NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=2;

--
-- AUTO_INCREMENT de la tabla `Proyecto`
--
ALTER TABLE `Proyecto`
  MODIFY `ID_Proyecto` int(10) UNSIGNED NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=2;

--
-- AUTO_INCREMENT de la tabla `Tarea`
--
ALTER TABLE `Tarea`
  MODIFY `ID_Tarea` int(10) UNSIGNED NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=2;

--
-- AUTO_INCREMENT de la tabla `Tipo`
--
ALTER TABLE `Tipo`
  MODIFY `ID_Tipo` int(10) UNSIGNED NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=2;

--
-- AUTO_INCREMENT de la tabla `Usuario`
--
ALTER TABLE `Usuario`
  MODIFY `ID_Usuario` int(10) UNSIGNED NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=3;

--
-- Restricciones para tablas volcadas
--

--
-- Filtros para la tabla `Alumno`
--
ALTER TABLE `Alumno`
  ADD CONSTRAINT `fk_alumno_usuario` FOREIGN KEY (`ID_Usuario`) REFERENCES `Usuario` (`ID_Usuario`) ON DELETE CASCADE ON UPDATE CASCADE;

--
-- Filtros para la tabla `Archivo`
--
ALTER TABLE `Archivo`
  ADD CONSTRAINT `fk_archivo_alumno` FOREIGN KEY (`ID_Alumno`) REFERENCES `Alumno` (`ID_Alumno`) ON DELETE CASCADE ON UPDATE CASCADE,
  ADD CONSTRAINT `fk_archivo_tipo` FOREIGN KEY (`ID_Tipo`) REFERENCES `Tipo` (`ID_Tipo`) ON UPDATE CASCADE;

--
-- Filtros para la tabla `Cursa`
--
ALTER TABLE `Cursa`
  ADD CONSTRAINT `fk_cursa_alumno` FOREIGN KEY (`ID_Alumno`) REFERENCES `Alumno` (`ID_Alumno`) ON DELETE CASCADE ON UPDATE CASCADE,
  ADD CONSTRAINT `fk_cursa_materia` FOREIGN KEY (`ID_Materia`) REFERENCES `Materias` (`ID_Materia`) ON DELETE CASCADE ON UPDATE CASCADE;

--
-- Filtros para la tabla `Materias`
--
ALTER TABLE `Materias`
  ADD CONSTRAINT `fk_materia_profesor` FOREIGN KEY (`ID_Profesor`) REFERENCES `Profesor` (`ID_Profesor`) ON UPDATE CASCADE;

--
-- Filtros para la tabla `Participa`
--
ALTER TABLE `Participa`
  ADD CONSTRAINT `fk_participa_alumno` FOREIGN KEY (`ID_Alumno`) REFERENCES `Alumno` (`ID_Alumno`) ON DELETE CASCADE ON UPDATE CASCADE,
  ADD CONSTRAINT `fk_participa_proyecto` FOREIGN KEY (`ID_Proyecto`) REFERENCES `Proyecto` (`ID_Proyecto`) ON DELETE CASCADE ON UPDATE CASCADE;

--
-- Filtros para la tabla `Profesor`
--
ALTER TABLE `Profesor`
  ADD CONSTRAINT `fk_profesor_usuario` FOREIGN KEY (`ID_Usuario`) REFERENCES `Usuario` (`ID_Usuario`) ON DELETE CASCADE ON UPDATE CASCADE;

--
-- Filtros para la tabla `Proyecto`
--
ALTER TABLE `Proyecto`
  ADD CONSTRAINT `fk_proyecto_materia` FOREIGN KEY (`ID_Materia`) REFERENCES `Materias` (`ID_Materia`) ON UPDATE CASCADE;

--
-- Filtros para la tabla `Tarea`
--
ALTER TABLE `Tarea`
  ADD CONSTRAINT `fk_tarea_proyecto` FOREIGN KEY (`ID_Proyecto`) REFERENCES `Proyecto` (`ID_Proyecto`) ON DELETE CASCADE ON UPDATE CASCADE;

--
-- Filtros para la tabla `Visualiza`
--
ALTER TABLE `Visualiza`
  ADD CONSTRAINT `fk_visualiza_profesor` FOREIGN KEY (`ID_Profesor`) REFERENCES `Profesor` (`ID_Profesor`) ON DELETE CASCADE ON UPDATE CASCADE,
  ADD CONSTRAINT `fk_visualiza_tarea` FOREIGN KEY (`ID_Tarea`) REFERENCES `Tarea` (`ID_Tarea`) ON DELETE CASCADE ON UPDATE CASCADE;
COMMIT;

/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
